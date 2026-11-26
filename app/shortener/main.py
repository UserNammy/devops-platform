import logging
import secrets
import string
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Path, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from shortener import __version__
from shortener.config import Settings, get_settings
from shortener.db import Base, get_session, make_engine, make_sessionmaker
from shortener.metrics import LINKS_CREATED, REDIRECTS, instrument
from shortener.models import Link
from shortener.schemas import CODE_PATTERN, LinkCreate, LinkOut

logger = logging.getLogger("shortener")

ALPHABET = string.ascii_letters + string.digits
MAX_CODE_ATTEMPTS = 5


def generate_code(length: int) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level.upper())

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = make_engine(settings.database_url)
        # The schema is created on startup to keep the demo self-contained.
        # A production service would run Alembic migrations as a separate step.
        Base.metadata.create_all(engine)
        app.state.engine = engine
        app.state.session_factory = make_sessionmaker(engine)
        logger.info("shortener %s started", __version__)
        yield
        engine.dispose()

    app = FastAPI(title="shortener", version=__version__, lifespan=lifespan)
    instrument(app)

    def to_out(link: Link) -> LinkOut:
        return LinkOut(
            code=link.code,
            target_url=link.target_url,
            short_url=f"{settings.base_url.rstrip('/')}/{link.code}",
            clicks=link.clicks,
            created_at=link.created_at,
        )

    def get_link_or_404(session: Session, code: str) -> Link:
        link = session.scalar(select(Link).where(Link.code == code))
        if link is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="link not found")
        return link

    # --- Operational endpoints (registered before the catch-all redirect) ---

    @app.get("/health", tags=["ops"])
    def health() -> dict[str, str]:
        """Liveness probe: the process is up and serving requests."""
        return {"status": "ok"}

    @app.get("/ready", tags=["ops"])
    def ready(session: Session = Depends(get_session)) -> dict[str, str]:
        """Readiness probe: the database is reachable."""
        try:
            session.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            logger.warning("readiness check failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="database unavailable"
            ) from exc
        return {"status": "ready"}

    # --- Links API ---

    @app.post("/api/links", status_code=status.HTTP_201_CREATED, tags=["links"])
    def create_link(payload: LinkCreate, session: Session = Depends(get_session)) -> LinkOut:
        attempts = 1 if payload.code else MAX_CODE_ATTEMPTS
        for _ in range(attempts):
            code = payload.code or generate_code(settings.code_length)
            link = Link(code=code, target_url=str(payload.url))
            session.add(link)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                continue
            session.refresh(link)
            LINKS_CREATED.inc()
            return to_out(link)

        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="code already in use")

    @app.get("/api/links/{code}", tags=["links"])
    def get_link(
        code: str = Path(pattern=CODE_PATTERN), session: Session = Depends(get_session)
    ) -> LinkOut:
        return to_out(get_link_or_404(session, code))

    @app.delete("/api/links/{code}", status_code=status.HTTP_204_NO_CONTENT, tags=["links"])
    def delete_link(
        code: str = Path(pattern=CODE_PATTERN), session: Session = Depends(get_session)
    ) -> None:
        session.delete(get_link_or_404(session, code))
        session.commit()

    @app.get("/{code}", tags=["links"], response_class=RedirectResponse)
    def follow_link(
        code: str = Path(pattern=CODE_PATTERN), session: Session = Depends(get_session)
    ) -> RedirectResponse:
        # One atomic statement: increment the counter and fetch the target.
        target = session.scalar(
            update(Link)
            .where(Link.code == code)
            .values(clicks=Link.clicks + 1)
            .returning(Link.target_url)
        )
        if target is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="link not found")
        session.commit()
        REDIRECTS.inc()
        return RedirectResponse(target, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    return app


app = create_app()
