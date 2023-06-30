from scenario import *


def with_leadership(state: State):
    return state.with_leadership(True)


def with_foo_relation(state: State):
    return state.replace(
        relations=[
            Relation(
                "foo",
                remote_app_data={"1": "2"}
            )
        ]
    )
