class SimulationError(Exception):
    pass


class IllegalActionError(SimulationError):
    pass


class SimModelError(SimulationError):
    pass
