"""Agent CRUD and messaging routes for the daemon API."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from squadron.core.agent_registry import (
    AgentAlreadyExistsError,
    AgentNotFoundError,
)
from squadron.core.models import AgentConfig, Message
from squadron.providers.errors import ProviderAuthError, ProviderError
from squadron.server.engine import SquadronEngine
from squadron.server.models import (
    AgentInfoOut,
    ErrorResponse,
    MessageOut,
    MessageRequest,
    MessageResponse,
    ShutdownReportOut,
    SpawnRequest,
    TaskRequest,
)

agents_router = APIRouter(prefix="/agents")


def _get_engine(request: Request) -> SquadronEngine:
    return request.app.state.engine  # type: ignore[no-any-return]


def _message_to_out(msg: Message) -> MessageOut:
    return MessageOut(
        id=msg.id,
        sender=msg.sender,
        content=msg.content,
        message_type=msg.message_type.value,
        timestamp=msg.timestamp,
        metadata=msg.metadata,
    )


@agents_router.post("/", response_model=AgentInfoOut)
async def spawn_agent(body: SpawnRequest, request: Request) -> AgentInfoOut:
    """Spawn a new agent."""
    engine = _get_engine(request)
    resolved_provider = body.provider or body.agent_type
    config = AgentConfig(
        name=body.name,
        agent_type=body.agent_type,
        provider=resolved_provider,
        model=body.model,
        instructions=body.instructions,
        base_url=body.base_url,
        cwd=body.cwd,
        api_key=body.api_key,
        credentials=body.credentials,
    )
    try:
        info = await engine.spawn_agent(config)
    except AgentAlreadyExistsError:
        return JSONResponse(  # type: ignore[return-value]
            status_code=409,
            content=ErrorResponse(detail=f"Agent '{body.name}' already exists").model_dump(),
        )
    except ProviderAuthError as exc:
        return JSONResponse(  # type: ignore[return-value]
            status_code=401,
            content=ErrorResponse(detail=str(exc)).model_dump(),
        )
    except ProviderError as exc:
        return JSONResponse(  # type: ignore[return-value]
            status_code=502,
            content=ErrorResponse(detail=str(exc)).model_dump(),
        )
    except KeyError as exc:
        return JSONResponse(  # type: ignore[return-value]
            status_code=400,
            content=ErrorResponse(detail=str(exc)).model_dump(),
        )

    return AgentInfoOut(
        name=info.name,
        agent_type=info.agent_type,
        provider=info.provider,
        state=info.state.value,
    )


@agents_router.get("/", response_model=list[AgentInfoOut])
async def list_agents(
    request: Request,
    state: str | None = None,
    provider: str | None = None,
) -> list[AgentInfoOut]:
    """List active agents, optionally filtered."""
    engine = _get_engine(request)
    agents = engine.list_agents(state=state, provider=provider)
    return [
        AgentInfoOut(
            name=a.name,
            agent_type=a.agent_type,
            provider=a.provider,
            state=a.state.value,
        )
        for a in agents
    ]


@agents_router.get("/{name}", response_model=AgentInfoOut)
async def get_agent(name: str, request: Request) -> AgentInfoOut | JSONResponse:
    """Get info for a single agent."""
    engine = _get_engine(request)
    try:
        agent = engine.get_agent(name)
    except AgentNotFoundError:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(detail=f"Agent '{name}' not found").model_dump(),
        )
    # Need provider from registry config
    config = engine.registry._configs.get(name)  # pyright: ignore[reportPrivateUsage]
    provider = config.provider if config else "unknown"
    return AgentInfoOut(
        name=agent.name,
        agent_type=agent.agent_type,
        provider=provider,
        state=agent.state.value,
    )


@agents_router.delete("/", response_model=ShutdownReportOut)
async def shutdown_all(request: Request) -> ShutdownReportOut:
    """Shut down all agents."""
    engine = _get_engine(request)
    report = await engine.shutdown_all()
    return ShutdownReportOut(
        succeeded=report.succeeded,
        failed=report.failed,
    )


@agents_router.delete("/{name}")
async def shutdown_agent(name: str, request: Request) -> Response:
    """Shut down a single agent."""
    engine = _get_engine(request)
    try:
        await engine.shutdown_agent(name)
    except AgentNotFoundError:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(detail=f"Agent '{name}' not found").model_dump(),
        )
    return Response(status_code=204)


@agents_router.post("/{name}/message", response_model=MessageResponse)
async def send_message(
    name: str, body: MessageRequest, request: Request
) -> MessageResponse | JSONResponse:
    """Send a message to an agent and return responses."""
    engine = _get_engine(request)
    try:
        responses = await engine.send_message(name, body.content)
    except AgentNotFoundError:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(detail=f"Agent '{name}' not found").model_dump(),
        )
    return MessageResponse(messages=[_message_to_out(m) for m in responses])


@agents_router.post("/{name}/task", response_model=MessageResponse)
async def run_task(name: str, body: TaskRequest, request: Request) -> MessageResponse | JSONResponse:
    """One-shot task: spawn ephemeral agent, message, shut down."""
    engine = _get_engine(request)
    resolved_provider = body.provider or body.agent_type
    config = AgentConfig(
        name=body.name,
        agent_type=body.agent_type,
        provider=resolved_provider,
        model=body.model,
        instructions=body.instructions,
        base_url=body.base_url,
        cwd=body.cwd,
        api_key=body.api_key,
    )
    try:
        await engine.spawn_agent(config)
        responses = await engine.send_message(config.name, body.prompt)
        await engine.shutdown_agent(config.name)
    except ProviderError as exc:
        return JSONResponse(
            status_code=502,
            content=ErrorResponse(detail=str(exc)).model_dump(),
        )
    except KeyError as exc:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(detail=str(exc)).model_dump(),
        )
    return MessageResponse(messages=[_message_to_out(m) for m in responses])


@agents_router.get("/{name}/history", response_model=MessageResponse)
async def get_history(name: str, request: Request, limit: int | None = None) -> MessageResponse:
    """Get conversation history for an agent."""
    engine = _get_engine(request)
    history = engine.get_history(name)
    if limit is not None:
        history = history[-limit:]
    return MessageResponse(messages=[_message_to_out(m) for m in history])
