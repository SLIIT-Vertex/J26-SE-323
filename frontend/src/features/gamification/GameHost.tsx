import { lazy, Suspense, useCallback, useRef, useState } from "react";

import type { StepView } from "./api/generated";
import {
  DEV_LEARNER_ID,
  PILOT_SKILL_ID,
  PilotApiError,
  PilotClient,
  type DecisionModeName,
} from "./api/pilotClient";
import { useReducedMotion } from "./accessibility/reducedMotion";
import { SupportLayer } from "./support/SupportLayer";

const BuildManipulate = lazy(() =>
  import("./phaser/templates/build-manipulate/BuildManipulate").then((module) => ({
    default: module.BuildManipulate,
  })),
);
import { TelemetryQueue } from "./telemetry/queue";
import { ChoiceQuest } from "./templates/ChoiceQuest";

type QuestionPhase = "baseline" | "verification";

type PlayState =
  | { status: "idle" }
  | { status: "question"; step: StepView; selected: string | null; phase: QuestionPhase }
  | { status: "support"; step: StepView }
  | { status: "done"; episodeId: string; nextStep: string }
  | { status: "error"; message: string };

export function GameHost({ client = new PilotClient() }: { client?: PilotClient }) {
  const reducedMotion = useReducedMotion();
  const [mode, setMode] = useState<DecisionModeName>("performance_triggered_fixed");
  const [state, setState] = useState<PlayState>({ status: "idle" });
  const sessionId = useRef<string | null>(null);
  const presentedAt = useRef(Date.now());
  const answering = useRef(false);
  const selectedRef = useRef<string | null>(null);
  const queue = useRef(new TelemetryQueue());

  const flush = useCallback(async () => {
    const current = sessionId.current;
    const batch = queue.current.take();
    if (!current || !batch) return;
    try {
      await client.sendEvents(current, DEV_LEARNER_ID, batch, crypto.randomUUID());
    } catch {
      queue.current.restore(batch);
    }
  }, [client]);

  const choose = useCallback(
    (optionId: string) => {
      if (!answering.current) return;
      queue.current.record(selectedRef.current ? "option_changed" : "option_selected", {
        option_id: optionId,
      });
      selectedRef.current = optionId;
      setState((current) =>
        current.status === "question" ? { ...current, selected: optionId } : current,
      );
      void flush();
    },
    [flush],
  );

  async function start() {
    try {
      const session = await client.createSession(
        {
          learner_id: DEV_LEARNER_ID,
          client_session_id: crypto.randomUUID(),
          language: "si",
        },
        crypto.randomUUID(),
      );
      sessionId.current = session.session_id;
      const step = await client.nextActivity(
        session.session_id,
        DEV_LEARNER_ID,
        {
          skill_id: PILOT_SKILL_ID,
          device_capabilities: ["choice_quest", "build_manipulate"],
        },
        crypto.randomUUID(),
        mode,
      );
      presentQuestion(step, "baseline");
    } catch (error) {
      setState({ status: "error", message: messageOf(error) });
    }
  }

  function presentQuestion(step: StepView, phase: QuestionPhase) {
    answering.current = true;
    selectedRef.current = null;
    presentedAt.current = Date.now();
    queue.current.record(phase === "baseline" ? "item_presented" : "verification_presented", {
      item_id: step.manifest?.item_id ?? "",
    });
    setState({ status: "question", step, selected: null, phase });
    void flush();
  }

  async function submit() {
    if (state.status !== "question" || !state.selected || !sessionId.current || !state.step.manifest) {
      return;
    }
    const eventType = state.phase === "verification" ? "verification_submitted" : "answer_submitted";
    queue.current.record(eventType, { option_id: state.selected });
    try {
      const step = await client.submitResponse(
        sessionId.current,
        DEV_LEARNER_ID,
        {
          episode_id: state.step.episode_id,
          selected_option_id: state.selected,
          response_time_ms: Date.now() - presentedAt.current,
        },
        crypto.randomUUID(),
      );
      if (step.next_step === "present_support" && step.support) {
        answering.current = false;
        queue.current.record("support_presented", { scaffold_type: step.support.scaffold_type });
        setState({ status: "support", step });
      } else if (step.next_step === "present_verification" && step.manifest) {
        presentQuestion(step, "verification");
      } else {
        finish(step);
      }
      await flush();
    } catch (error) {
      setState({ status: "error", message: messageOf(error) });
    }
  }

  async function continueAfterSupport() {
    if (state.status !== "support" || !state.step.support || !sessionId.current) return;
    const episodeId = state.step.episode_id;
    queue.current.record("support_dismissed", {});
    try {
      await client.completeSupport(
        episodeId,
        DEV_LEARNER_ID,
        {
          duration_ms: Date.now() - presentedAt.current,
          step_count: state.step.support.steps.length,
        },
        crypto.randomUUID(),
      );
      queue.current.record("support_withdrawn", {});
      const step = await client.withdrawSupport(episodeId, DEV_LEARNER_ID, crypto.randomUUID());
      if (step.next_step === "present_verification" && step.manifest) presentQuestion(step, "verification");
      else finish(step);
      await flush();
    } catch (error) {
      setState({ status: "error", message: messageOf(error) });
    }
  }

  function finish(step: StepView) {
    answering.current = false;
    sessionStorage.setItem("pilot-episode-id", step.episode_id);
    setState({ status: "done", episodeId: step.episode_id, nextStep: step.next_step });
    if (sessionId.current) {
      void client.completeSession(sessionId.current, DEV_LEARNER_ID, crypto.randomUUID());
    }
  }

  const step = state.status === "question" || state.status === "support" ? state.step : null;
  const manifest = step?.manifest ?? null;
  const support = state.status === "support" ? state.step.support : null;

  return (
    <section className="game-host" data-motion={reducedMotion ? "reduced" : "full"}>
      <p className="eyebrow">Adult tester · NOT_FOR_PRODUCTION</p>
      <h2>Pilot episode</h2>
      {state.status === "idle" || state.status === "error" ? (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void start();
          }}
        >
          <label>
            Decision mode
            <select
              value={mode}
              onChange={(event) => setMode(event.target.value as DecisionModeName)}
            >
              <option value="performance_triggered_fixed">performance_triggered_fixed</option>
              <option value="shadow">shadow</option>
            </select>
          </label>
          <button type="submit">Start episode</button>
        </form>
      ) : null}
      {state.status === "error" ? <p role="alert">{state.message}</p> : null}
      {manifest && (state.status === "question" || state.status === "support") ? (
        <div className={state.status === "support" ? "locked-activity" : undefined}>
          {manifest.template_key === "build_manipulate" && state.status === "question" ? (
            <Suspense fallback={<p>Loading the fraction bar…</p>}>
              <BuildManipulate manifest={manifest} reducedMotion={reducedMotion} onSelect={choose} />
            </Suspense>
          ) : (
            <ChoiceQuest
              manifest={manifest}
              selectedOptionId={state.status === "question" ? state.selected : null}
              reducedMotion={reducedMotion}
              onSelect={state.status === "question" ? choose : () => undefined}
            />
          )}
        </div>
      ) : null}
      <SupportLayer support={support} reducedMotion={reducedMotion} />
      {state.status === "question" ? (
        <button type="button" onClick={() => void submit()} disabled={!state.selected}>
          Submit answer
        </button>
      ) : null}
      {state.status === "support" ? (
        <button type="button" onClick={() => void continueAfterSupport()}>
          Continue
        </button>
      ) : null}
      {state.status === "done" ? (
        <p>
          Episode {state.episodeId} ended with {state.nextStep}. Open the inspector to reconstruct
          it.
        </p>
      ) : null}
    </section>
  );
}

function messageOf(error: unknown): string {
  return error instanceof PilotApiError ? error.code : "REQUEST_FAILED";
}
