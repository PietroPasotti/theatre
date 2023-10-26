Theatre
=======

Theatre is a [scenario](https://github.com/canonical/ops-scenario)-based charm state-transition driver.

![screenshot.png](theatre%2Fresources%2Fbranding%2Fscreenshot.png)

Theatre allows you to create elaborate (simulated) charm execution trees, powered by scenario.

All trees start with a root node.
The root node represents the initial state of your charm. The simplest of them is the 'null' state: one where your charm has no relations, no containers, no networks, no leadership...

![state-pic.png](theatre%2Fresources%2Fbranding%2Fstate-pic.png)

You can evolve that state in two ways:
- emitting an `event` and obtain the output state (i.e. the state after the charm has interacted with the initial state given the event)
- adding a `delta` to that state. You can think of a delta as a non-destructive additional layer on top of the state. So if your initial state has no relations, you could add a delta to it that adds one or more relations. The delta'ed state would then be "the same as the initial state, _but with this and that relation on top_".

The core mechanism of `theatre` is to fire events on states. 

Emit an event in `theatre` by drag-dropping the output nodes of a node.
Events are represented by edges.

![edge-pic.png](theatre%2Fresources%2Fbranding%2Fedge-pic.png)

Deltas are represented by small node-looking boxes at the bottom of nodes representing states.

![node-deltas-pic.png](theatre%2Fresources%2Fbranding%2Fnode-deltas-pic.png)

A branch in the tree corresponds to an execution `trace`, that is a possible path your charm state evolution will take, depending on what events it sees. 
The trace of a state represents its history.
You can see what a trace looks like by clicking on a node and viewing the Trace Inspector pane.
![trace-pic.png](theatre%2Fresources%2Fbranding%2Ftrace-pic.png)

You can inspect individual nodes by clicking on their item on the trace inspector. That will display on a pane on the side their raw contents (i.e. the `scenario.State`) dataclass, and any logs that were emitted during the charm execution that led to this state. 


Dynamic subtrees
================

Theatre has a _Library_ feature, that allows you to drop into a tree a few built-in objects (and in the future, who knows, maybe your own custom ones). 

![library-pic.png](theatre%2Fresources%2Fbranding%library-pic.png)

There are four types of objects in the library:
- **static nodes**: these are hardcoded simple nodes, such as the null state node, or the 'leader state', where the state is equivalent to `State(leader=True)`.
- **dynamic nodes**: these are nodes that are dynamically generated based on the charm that you are working on. For example, the "Null with containers" node will drop a node with a State containing all containers that your charm defines in metadata. Roughly equivalent to `State(containers=[Container(name=name) for name in charm_metadata_yaml['containers']])`.
- **static subtrees**: these are hardcoded simple subtrees that can be attached to any node in a graph. For example the "bare startup sequence" subtree will attach a `install -> config_changed -> start` event sequence (and corresponding intermediate nodes) to a node of your choice. 
- **dynamic subtrees**: these are subtrees that are dynamically generated based on the node that they are attached to (aka dropped on). For example the 'fan out' dynamic subtree will generate all possible state transitions for a given node (so, for each container, a `-pebble-ready`, for each relation, a `-relation-changed`, a `-relation-created`, and so on). This is great for fuzzing a charm and checking if there is a path that breaks things. Do note that not all transitions are guaranteed to be 'consistent' in terms of event ordering.


Filesystems
===========

When scenario runs an event on a state, it attaches a simulated filesystem to each container you passed. This filesystem is clean and assumed to be isolated, i.e. scenario doesn't persist any changes between `scenario.Context.run` calls.

Theatre takes a slightly different approach because, in Theatre, the sequence does matter. Simplifying a little, Theatre feeds the output filesystem of each execution into the next execution. So the filesystem will grow and evolve with each event the charm sees. This way, you can verify that the filesystem is changing the way you expect it to, without having to do manually the bookkeeping of deciding which initial contents each filesystem has, for all of the nodes in your tree.

You can right-click on a node and select the 'inspect virtual filesystem' option to open the root temporary folder for the charm. In there, you will find a subfolder for each container your charm has.


Caching and dependency
======================

Root nodes have a fixed, statically assigned State as value.
Non-root nodes depend on the value of their input node (i.e. their starting state) and an incoming event-edge for their value. If that value cannot be obtained (e.g. because the charm raises an exception while handling that event), the node will be marked invalid. You can see that by a red circle on top of the node. 

You can mark a node 'dirty', thereby discarding any cached value and resetting the invalid state. Dirty nodes are marked orange.

If the execution goes well and the node is able to obtain a valid output state, that state becomes its value and the node is marked valid. Valid nodes are marked green.

![node-statuses-pic.png](theatre%2Fresources%2Fbranding%2Fnode-statuses-pic.png)

You can evaluate a node by clicking on it. If a node is valid and has not been marked dirty (aka manually invalidated), reevaluating the node will do effectively nothing. If you want to force-reevaluate a node, you can do so from the right-click menu. 

Disclaimers
===========

This is an experimental tool under heavy development.

We plan to be able to use it to:
- aid charm development
- aid charm debugging
- aid writing scenario tests for charms

Stay tuned!

Quickstart
==========

Cd to a charm project. 
Activate the venv you use to run (scenario) tests for that charm.
Build and install `theatre`.
Create a file called `run_theatre.py` containing:

    import os
    from pathlib import Path
    from theatre.main import show_main_window
    show_main_window(Path(os.getcwd()))

Run that file with 

    PYTHONPATH=./:./lib:./src python ./run_theatre.py

Theatre should guide you through the initialization of a `.theatre` dir in that charm repo. In there, you'll find a `loader.py` file that you should edit to give `theatre` a `scenario.Context` suitable for locally running your charm. Make sure to patch all calls to system, pebble, or substrate (e.g. lightkube) APIs that are not wrapped by Scenario.

You're ready to go! 


Development
===========

- Tested with python 3.11
- Scenario 5.5
