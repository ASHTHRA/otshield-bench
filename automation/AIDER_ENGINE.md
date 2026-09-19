# Aider local editing engine

The strict autonomous verifier is unchanged.

Local implementation attempts now use:
- Aider as the code-editing agent
- Ollama as the local inference server
- qwen2.5-coder:7b-instruct as the local code model
- 8192-token Ollama context
- whole-file edit format
- no Aider auto-commits

A task is accepted only by the existing strict git/test/build gates.
