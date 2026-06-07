"""
Experiment file to assist in designing the director agent.
"""

import os

from world_simulation_engine.misc.enums import LlmProvider
from world_simulation_engine.model.connection_profile import LlmConnectionProfile
from world_simulation_engine.model.data_preset import DataPresetModel, DataPreset
from world_simulation_engine.model.agent_preset import OllamaAgentProfile
from world_simulation_engine.model.simulation import Simulation
from world_simulation_engine.service.world_agent.director_agent import DirectorAgent


OLLAMA_URL = os.getenv("EXP_OLLAMA_URL")
OLLAMA_MODEL = os.getenv("EXP_OLLAMA_MODEL")


async def experiment_director_agent(agent: DirectorAgent):



def main():
    director_agent = DirectorAgent(
        profile=OllamaAgentProfile(
            connection=LlmConnectionProfile(
                provider=LlmProvider.OLLAMA,
                base_url=OLLAMA_URL,
            ),
            model=OLLAMA_MODEL,
            temperature=0.4,
            context_window=65536,
            prompts=[],
        ),
    )
