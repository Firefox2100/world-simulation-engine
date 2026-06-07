from world_simulation_engine.model.data_preset import DataPreset
from world_simulation_engine.model.simulation import Simulation


example_simulation = Simulation(
    id=1,
    name="Example Simulation",
    description="An example simulation",
    data_preset=DataPreset()
)
