export const CLASSROOM_ASSET_ROOT = "/curriculum/game/G5-AREA-ENG-01";

export const CLASSROOM_SKILLS = [
	{
		id: "G5-ENG-BEH-POSTURE-01",
		chapter: "action_mirror",
		name: "Action Mirror",
		description: "Read an English command and change the character's pose.",
		asset: "student-arms-stretched.png",
	},
	{
		id: "G5-ENG-BEH-DESTINATION-01",
		chapter: "classroom_dash",
		name: "Classroom Dash",
		description: "Move to the wall or the blackboard.",
		asset: "student-running.png",
	},
	{
		id: "G5-ENG-BEH-RETURN-01",
		chapter: "come_back",
		name: "Come Back Quest",
		description: "Return to the place where the journey began.",
		asset: "start-position-mat.png",
	},
] as const;

export const ACTION_ASSETS: Record<string, string> = {
	bend: "student-bending.png",
	stretch_arms: "student-arms-stretched.png",
	arms_down: "student-arms-down.png",
	stand_straight: "student-standing-straight.png",
	turn_around: "student-turned-around.png",
	sit_down: "student-sitting.png",
};

export const ACTION_LABELS: Record<string, { en: string; si: string }> = {
	bend: { en: "Bend", si: "නැමෙන්න" },
	stretch_arms: { en: "Stretch your arms", si: "ඔබේ අත් දිගහරින්න" },
	arms_down: { en: "Put your arms down", si: "ඔබේ අත් පහළට දමන්න" },
	stand_straight: { en: "Stand straight", si: "කෙළින් සිටගන්න" },
	turn_around: { en: "Turn around", si: "වටයකට හැරෙන්න" },
	sit_down: { en: "Sit down", si: "වාඩිවෙන්න" },
};
