---
icon: lucide/rocket
---

# World Simulation Engine

The World Simulation Engine is an experimental project to use a multi-agent architecture to power role-play sessions. It's not designed to be a production or efficient system, but to answer one question: how far can we go with a multi-agent architecture to simulate a world and its inhabitants?

## License and Disclaimer

The World Simulation Engine is licensed under the MIT License. This means you are free to use, modify, and distribute the software, but it comes with no warranty. The developers are not responsible for any issues that may arise from using the software. Refer to the [LICENSE file](https://raw.githubusercontent.com/Firefox2100/world-simulation-engine/refs/heads/main/LICENSE) for more details.

This software is intended for local usage only. As a result, it lacks any form of security or privacy measures. It's strongly advised against using this software in any environment where security and privacy are a concern, such as exposing it to the internet or on a computer shared with others.

This software connects to external services, such as cloud LLM providers, which may have their own Terms of Service and Privacy Policies. Users are responsible for understanding and complying with these terms when using the software. There is no built-in security mechanism to prevent certain text being sent, including sensitive personal information. There is also no built-in filtering mechanism to prevent the generation of harmful or inappropriate content. Users are responsible for ensuring that their use of the software complies with all applicable laws and regulations.

There are logos, icons and names of third-party services used in this software, which are the property of their respective owners. The use of these logos, icons and names does not imply any endorsement or affiliation with the respective owners. This software is not endorsed by or affiliated with any third-party service providers, and the use of their logos, icons and names is for informational purposes only.

## Features

This software uses complicated multi-agent architecture and structured states to try to maintain the consistency and continuity of a simulated session. Some important features include:

- **Multi-agent architecture**: Each agent is responsible for a different step in the simulation process, with a scoped knowledge and information. This prevents information leaking and fact drift, and allows for more complex and realistic simulations. Each agent can be configured separately, including their provider, model, prompt, and other parameters.
- **Structured states**: The software maintains a structured state of the simulation, stored into the database, instead of just the narrated text. This allows for more complex and realistic management of the state.
- **First class support for media generation**: The software has first class support for media generation, including image, video and audio (WIP). This allows for more immersive and engaging simulations.
- **Local first design**: Unlike some popular systems which is designed to leverage the advanced capabilities of cloud flagship models, this software is designed to work with reasonably good local models, for maximum privacy and security.

Please refer to the corresponding sections in the documentation for more details on each feature, and how to use them.
