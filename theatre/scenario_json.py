"""Library to deserialize json data as scenario.state dataclasses."""

# TODO: move to scenario

from scenario.state import *

from scenario.state import _EntityStatus


def _convert_if_not_none(source: dict, key: str,
                         converter: typing.Callable[[dict], typing.Any] = lambda x: x,
                         default: typing.Any = None):
    if value := source.get(key, None):
        return converter(value)
    return default


def parse_action(obj: dict) -> Action:
    return Action(**obj)


def parse_container(obj: dict) -> Container:
    return Container(**obj)  # this won't work for long, alas


def parse_relation(obj: dict) -> Relation:
    return Relation(**obj)  # this won't work for long, alas


def parse_secret(obj: dict) -> Secret:
    return Secret(**obj)  # this won't work for long, alas


def parse_event(obj: dict) -> Event:
    return Event(
        action=_convert_if_not_none(obj, 'action', parse_action),
        args=_convert_if_not_none(obj, 'args', lambda x: x),
        container=_convert_if_not_none(obj, 'container', parse_container),
        kwargs=_convert_if_not_none(obj, 'kwargs', lambda x: x, {}),
        name=_convert_if_not_none(obj, 'name'),
        relation=_convert_if_not_none(obj, 'relation', parse_relation),
        relation_remote_unit_id=_convert_if_not_none(obj, 'relation_remote_unit_id'),
        secret=_convert_if_not_none(obj, 'secret', parse_secret),
    )


def parse_status(obj: dict) -> _EntityStatus:
    return _EntityStatus(**obj)


def parse_model(obj: dict) -> Model:
    return Model(**obj)


def parse_network(obj: dict) -> Network:
    return Network(**obj)


def parse_deferred(obj: dict) -> DeferredEvent:
    return DeferredEvent(**obj)


def parse_storedstate(obj: dict) -> StoredState:
    return StoredState(**obj)


def parse_state(obj: dict) -> State:
    return State(
        config=_convert_if_not_none(
            obj, "config", default={}
        ),
        relations=_convert_if_not_none(
            obj, "relations", lambda x: [parse_relation(r) for r in x], []
        ),
        networks=_convert_if_not_none(
            obj, "networks", lambda x: [parse_network(r) for r in x], []
        ),
        containers=_convert_if_not_none(
            obj, "containers", lambda x: [parse_container(r) for r in x], []
        ),
        leader=_convert_if_not_none(
            obj, "leader", default=False
        ),
        model=_convert_if_not_none(
            obj, "model", parse_model, Model()
        ),
        secrets=_convert_if_not_none(
            obj, "secrets", lambda x: [parse_secret(r) for r in x], []
        ),
        unit_id=_convert_if_not_none(
            obj, "unit_id", default=0
        ),
        deferred=_convert_if_not_none(
            obj, "deferred", lambda x: [parse_deferred(r) for r in x], []
        ),
        stored_state=_convert_if_not_none(
            obj, "stored_state", lambda x: [parse_storedstate(r) for r in x], []
        ),
        app_status=_convert_if_not_none(
            obj, "app_status", parse_status, ""
        ),
        unit_status=_convert_if_not_none(
            obj, "unit_status", parse_status, ""
        ),
        workload_version=_convert_if_not_none(
            obj, "workload_version"
        ),
    )
