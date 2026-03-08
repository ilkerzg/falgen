"""get_skill tool — loads domain knowledge for better generation."""

from .base import Tool


class GetSkillTool(Tool):
    name = "get_skill"
    description = (
        "Load domain knowledge progressively — start broad, drill down only as needed. "
        "1) get_skill(name) → TOC + quick reference cheat sheet. Often enough for simple tasks. "
        "2) get_skill(name, section='key') → section content. Small sections load fully. "
        "   Large sections return a sub-TOC listing their subsections. "
        "3) get_skill(name, section='subsection_key') → specific subsection (e.g. 'veo_3_1'). "
        "Start with the TOC. The quick reference covers 80% of use cases. "
        "Only drill deeper when you need specific model parameters or detailed techniques."
    )
    parameters = {
        "properties": {
            "skill_name": {
                "type": "string",
                "description": (
                    "Skill to load. Available: cinematography, video_prompting, "
                    "image_prompting, commercial, audio_prompting, workflow_utils, "
                    "character_design, storytelling, social_media, motion_design, "
                    "world_building, brand_identity"
                ),
                "enum": [
                    "cinematography",
                    "video_prompting",
                    "image_prompting",
                    "commercial",
                    "audio_prompting",
                    "workflow_utils",
                    "character_design",
                    "storytelling",
                    "social_media",
                    "motion_design",
                    "world_building",
                    "brand_identity",
                ],
            },
            "section": {
                "type": "string",
                "description": (
                    "Section or subsection key to load. Omit to get TOC. "
                    "Use a key from the TOC or sub-TOC. Supports fuzzy matching "
                    "(e.g. 'veo' matches 'veo_3_1_google_flagship')."
                ),
            },
        },
        "required": ["skill_name"],
    }

    def execute(self, args: dict) -> dict:
        from ..skills import list_skills, load_skill_section, load_skill_toc

        name = args.get("skill_name", "")
        section = args.get("section")

        if section:
            content = load_skill_section(name, section)
            if content is None:
                available = [s["name"] for s in list_skills() if s["available"]]
                return {
                    "ok": False,
                    "error": f"Skill '{name}' not found or not available",
                    "available_skills": available,
                }
            return {
                "ok": True,
                "skill": name,
                "section": section,
                "content": content,
            }
        else:
            content = load_skill_toc(name)
            if content is None:
                available = [s["name"] for s in list_skills() if s["available"]]
                return {
                    "ok": False,
                    "error": f"Skill '{name}' not found or not available",
                    "available_skills": available,
                }
            return {
                "ok": True,
                "skill": name,
                "section": "toc",
                "content": content,
            }
