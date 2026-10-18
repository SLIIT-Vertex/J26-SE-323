import { type Mastery, type SkillMastery, getMastery } from "../api";
import { AREAS, type Area, percent } from "../format";
import { useAsync } from "../hooks";
import { hrefFor } from "../router";
import { ErrorBox, GrowthIcon, Loading, ScreenHeader, StoneMeter, type Tone } from "../ui";

// The same colours the game uses for its subjects: maths blue, language violet, environment green.
const AREA_TONE: Record<Area, Tone> = { APT: "sun", MAT: "sky", LAN: "violet", ENV: "mint" };

export function skillLine(skill: SkillMastery): string {
  if (skill.mastery === null) {
    return skill.attempts === 0
      ? "Not enough questions yet"
      : `Not enough questions yet (${skill.attempts} answered)`;
  }
  return `${percent(skill.mastery)}%`;
}

function SkillRow({ skill, tone }: { skill: SkillMastery; tone: Tone }) {
  const known = skill.mastery !== null;
  return (
    <li className="mb-skill">
      <div className="mb-skill__names">
        <strong>{skill.name_en}</strong>
        {skill.name_si ? (
          <small lang="si" className="mb-muted">
            {skill.name_si}
          </small>
        ) : null}
      </div>
      <StoneMeter value={skill.mastery} tone={tone} label={skillLine(skill)} />
      <span className={`mb-skill__value${known ? "" : " is-unknown"}`}>
        {skill.mastery === null ? "–" : `${percent(skill.mastery)}%`}
      </span>
      {known ? null : <small className="mb-skill__why">{skillLine(skill)}</small>}
    </li>
  );
}

function AreaSection({ area, skills }: { area: (typeof AREAS)[number]; skills: SkillMastery[] }) {
  const tone = AREA_TONE[area.code];
  const measured = skills.filter((s) => s.mastery !== null).length;
  return (
    <section className={`mb-area mb-area--${tone}`} aria-labelledby={`area-${area.code}`}>
      <div className="mb-area__head">
        <h2 id={`area-${area.code}`} className="mb-h2">
          {area.name}
        </h2>
        <span className="mb-area__count">
          {measured} of {skills.length} measured
        </span>
      </div>
      <p className="mb-muted">{area.blurb}</p>
      <ul className="mb-list mb-list--tight">
        {skills.map((skill) => (
          <SkillRow key={skill.code} skill={skill} tone={tone} />
        ))}
      </ul>
    </section>
  );
}

function Overview({ data }: { data: Mastery }) {
  const measured = data.skills.filter((s) => s.mastery !== null).length;
  return (
    <p className="mb-lead">
      <strong>
        {measured} of {data.skills.length}
      </strong>{" "}
      skills can be measured so far, from <strong>{data.n_attempts}</strong> answers in games and on paper.
    </p>
  );
}

export function MasteryScreen({ learnerId }: { learnerId: string }) {
  const { state, reload } = useAsync(() => getMastery(learnerId), `mastery:${learnerId}`);
  const data = state.status === "ready" ? state.data : null;

  return (
    <>
      <ScreenHeader
        title="How learning is going"
        kicker="My skills"
        back={{ href: hrefFor({ name: "papers" }), label: "Practice" }}
        icon={<GrowthIcon />}
      />
      <div className="mb-body-pad">
        {state.status === "loading" ? <Loading label="Working out the skills" /> : null}
        {state.status === "error" ? <ErrorBox message={state.message} onRetry={reload} /> : null}
        {data ? (
          <>
            <Overview data={data} />
            <p className="mb-fineprint">Each bar is the chance of answering a medium paper question correctly.</p>
            {AREAS.map((area) => (
              <AreaSection key={area.code} area={area} skills={data.skills.filter((s) => s.area === area.code)} />
            ))}
          </>
        ) : null}
      </div>
    </>
  );
}
