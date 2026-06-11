import asyncio
import json

from world_simulation_engine.service import MemoryAgent, EmbeddingService
from world_simulation_engine.model import DirectorOutput, ActivationDecision
from world_simulation_engine.component import WorldEntryRecaller

from example_simulation import example_world_entries, example_simulation_state, example_characters, \
    example_simulation, example_tasks, example_locations
from agent_configuration import memory_agent, embedding_service


async def generate_briefing(agent: MemoryAgent,
                            embedding_service: EmbeddingService,
                            ):
    current_location = next(l for l in example_locations if l.id == example_simulation_state.scene)
    director_output = DirectorOutput(
        scene_focus="Establish the atmosphere of the Founder's Festival within the Iron Stag Inn, focusing on "
                    "Clara's service and initial reception of Arthur as a new arrival, while maintaining "
                    "Eleanor's surveillance presence in the background without immediate confrontation.",
        activations=[
            ActivationDecision(
                character_id=3,
                character_name="Clara Whitlock",
                activate=True,
                priority=85,
                reason="Innkeeper duty requires greeting a new arrival during the busy festival; private "
                       "curiosity about the stranger's purpose drives her to observe him closely while serving.",
                private_motive_used=True
            ),
            ActivationDecision(
                character_id=1,
                character_name="Eleanor Graves",
                activate=False,
                priority=0,
                reason="Prefers to assess the investigator's behavior from a distance before engaging directly; "
                       "currently monitoring Arthur's initial movements without interrupting Clara's service.",
                private_motive_used=True
            ),
            ActivationDecision(
                character_id=4,
                character_name="Arthur Moore",
                activate=False,
                priority=0,
                reason="User-controlled character; awaiting user input to define specific action or dialogue in "
                       "response to the environment.",
                private_motive_used=False
            )
        ],
        wait_for_user=False,
        reason_to_wait="",
        director_notes="Clara's activation provides a safe entry point for Arthur (service/greeting) without "
                       "forcing plot progression. Eleanor remains passive to allow the player to establish "
                       "their own stance before facing the Mayor's scrutiny.",
    )
    pending_generated_proposals = []
    user_input = "Arthur remains at the bar and casually asks Clara whether Room 7 was occupied before Harlan vanished."

    active_characters = []
    for c in example_characters:
        activation = next((a for a in director_output.activations if a.character_id == c.id), None)
        if activation is not None and activation.activate:
            active_characters.append(c)
    active_character_ids = set([
        c.id for c in active_characters
    ])

    tasks = []
    for t in example_tasks:
        if bool(set(t.character_ids) & active_character_ids) and not t.private:
            tasks.append(t)

    world_entries = []
    for e in example_world_entries:
        if 0 in e.scope:
            world_entries.append(e)

    recaller = WorldEntryRecaller(
        embedding_service=embedding_service,
    )
    recalled_entries = await recaller.recall(
        query=director_output.scene_focus + " " + user_input,
        entries=world_entries,
        language=example_simulation.language,
    )

    print("Test direct generation with history:")
    result = await agent.build_briefings(
        simulation=example_simulation,
        state=example_simulation_state,
        current_location=current_location,
        characters=active_characters,
        tasks=tasks,
        world_entries=recalled_entries,
        pending_generated_proposals=pending_generated_proposals,
        user_input=user_input,
        last_narration="The Iron Stag Inn hummed with festival noise, glasses clinking beneath the low beams "
                       "while rain tapped against the windows. Clara moved behind the bar with practiced "
                       "cheer, but her eyes returned to Arthur more often than chance required. Eleanor "
                       "Graves had just left the doorway after offering a polished welcome, and several "
                       "locals pretended not to listen.",
        previous_resolver_notes="No active conflict remained from the previous round. Eleanor successfully "
                                "withdrew from the immediate conversation without revealing concern. Clara "
                                "is available at the bar and is socially positioned to answer or redirect "
                                "Arthur's questions.",
    )
    print("Briefing output:")
    print(json.dumps(result.model_dump(), indent=2))


async def experiment_memory_agent(agent: MemoryAgent,
                                  embedding_service: EmbeddingService,
                                  ):
    await generate_briefing(
        agent=agent,
        embedding_service=embedding_service,
    )


def main():
    asyncio.run(experiment_memory_agent(
        agent=memory_agent,
        embedding_service=embedding_service,
    ))


if __name__ == "__main__":
    main()
