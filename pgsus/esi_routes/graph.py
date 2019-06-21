"""Generic map graph to overlay."""


import os
import json


def _load_starmap():
    """Load the starmap from static data."""

    static = os.environ.get("STATIC_DATA", os.path.realpath(
        os.path.dirname(__file__)))

    jump_map = os.path.join(static, "jumpmap.json")

    if not os.path.isfile(jump_map):
        raise RuntimeError("missing data: {}".format(jump_map))

    with open(jump_map, "r") as open_jump_map:
        # JSON doesn't allow int keys
        return {int(k): v for k, v in json.load(open_jump_map).items()}


class Graph:
    """Created once during app init, this is the default universe."""

    def __init__(self, starmap=None):
        """Hold reference to the default starmap."""

        self._starmap = _load_starmap() if starmap is None else starmap

    def neighbors(self, system):
        """Return a list of neighbors for a given system."""

        return self.get_system(system)['neighbors']

    def ext_neighbors(self, system):
        return self.get_system(system)['e_neighbors']

    def security(self, system):
        """Return the security level for a given system."""

        return self.get_system(system)['security']

    def waypoint(self, system, dest_system):
        """Return the waypoint ID for a given system."""

        lookup = self.get_system(system)

        waypoints = lookup.get('waypoints')

        dest_waypoint = waypoints.get(dest_system) if waypoints is not None else None

        return dest_waypoint

    def get_system(self, system):
        """Return a dict with both neighbors and security for a system."""

        system_info = self._starmap.get(system)
        if system_info is None:
            raise RuntimeError("System not found: %s" % system)
        return system_info
