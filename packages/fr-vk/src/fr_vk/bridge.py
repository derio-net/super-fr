"""Runnable daemon entry — `python -m fr_vk.bridge`.

The canonical bridge invocation after the super-fr split (the pod's
cron wrapper execs this). `python -m fr_vk` works too via __main__.
"""

from fr_vk.bridge_cli import main

if __name__ == "__main__":
    main()
