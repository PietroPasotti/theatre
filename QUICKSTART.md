
# Set up your local development environment

> cd /path/to/charm/repo
> source /path/to/venv/activate  

ensure all python dependencies of the charm project are met. If necessary, run `pip install -e ./requirements.txt`.
If testing dependencies are present (all you'd require to run scenario tests, if you're familiar), install those too.

# Install theatre

> pip install git+https://github.com/PietroPasotti/theatre.git

# Create a startup file

```python
# run_theatre.py
if __name__ == '__main__':
    from theatre.main import show_main_window
    show_main_window()
```

# Execute the file with

> PYTHONPATH=./src:./lib:./ python ./run_theatre.py


# Initialize the charm repo

You should see a `.theatre` folder in `/path/to/charm/repo`.

```shell
tree ./.theatre                     
├── deltas_template.py         
├── loader.py                  
├── scenes                     
│    └── foo.json.theatre       
└── state.json                 
```

Edit `.theatre/loader.py` to contain, at the very least:


```python
import scenario
from charm import MyCharm

def charm_context() -> scenario.Context:
    """This function is expected to return a ready-to-run ``scenario.Context``.
    Edit this function as necessary.
    """
    return scenario.Context(charm_type=MyCharm)
```

If you need to do any sort of patching before this Context is ready to run, this is the place to do it.

For example:

```python
import scenario
from charm import MyCharm

from unittest.mock import patch, PropertyMock

def patch_all():
    for p in (
            patch("charm.KubernetesServicePatch"),
            # ... any other call or object you might want to mock
    ): 
        p.__enter__()

def charm_context() -> scenario.Context:
    """This function is expected to return a ready-to-run ``scenario.Context``.
    Edit this function as necessary.
    """
    patch_all()
    return scenario.Context(charm_type=MyCharm)
```


# Troubleshooting

If you have issues with xcb:
https://unix.stackexchange.com/a/338540
