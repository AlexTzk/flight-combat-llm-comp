# Local LLM competition

A repository containing the artifacts from 3 different tests across 9 local LLMs.

## Medium links:
- [Plane story](https://medium.com/@alexandru_vasile/i-made-9-local-llms-build-the-same-flight-combat-game-ed7136cc3560)
- [Bug hunt story](https://medium.com/@alexandru_vasile/which-local-llm-can-actually-review-code-i-tested-9-bbd05d134508)

## The models:
- Gemma 31B dense (Unsloth)
- Gemma 4 26B a4b (Unsloth)
- Qwen3.5 27B dense (MLX Community)
- Qwen3.5 35B A3B MoE (MLX Community)
- Qwen3.6 35B A3B — three different quants: oQ/oMLX, Unsloth, and MLX Community. Same model, three providers, and the quant differences matter more than I expected.
- Qwen3 Coder Next 80B (MLX Community)
- Qwopus 3.5 27B (the Opus-distilled Qwen, 8-bit MLX)


## Competition:
- First competition is a flight combat simulator game contained in 1 html file. [Open Prompt](./PROMPT.md)
- Second competition is a bug hunt task.[Open Prompt](./coding-task/PROMPT.md)

