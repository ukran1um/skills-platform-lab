"""FastAPI surface for the skill host. POST /run {skill, message, user} runs a blessed skill
in platform context. Governance failures map to HTTP: unknown skill -> 404; not blessed or
missing entitlement -> 403."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from skill_host.errors import EntitlementError, SkillNotBlessedError, SkillNotFoundError
from skill_host.host import HostConfig, Runner, _default_runner, run_skill_request


class RunBody(BaseModel):
    skill: str
    message: str
    user: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def create_app(*, config: HostConfig | None = None, runner: Runner = _default_runner) -> FastAPI:
    root = _repo_root()
    cfg = config or HostConfig(
        skills_dir=root / "skills", registry_dir=root / "registry",
        entitlements_path=root / "registry" / "entitlements.yaml")
    app = FastAPI(title="skills-platform-lab skill host")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/run")
    async def run(body: RunBody) -> dict[str, Any]:
        try:
            resp = await run_skill_request(body.skill, body.message, body.user,
                                           config=cfg, runner=runner)
        except SkillNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (SkillNotBlessedError, EntitlementError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        return {"skill": resp.skill, "status": resp.status, "user": resp.user,
                "scopes": resp.scopes, "final_text": resp.final_text,
                "trajectory": resp.trajectory}

    return app


def main() -> None:
    import uvicorn
    uvicorn.run(create_app(), host="127.0.0.1", port=8082)


if __name__ == "__main__":
    main()
