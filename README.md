# Beets AI Sauce Plugin
*Because your tunes deserve a little extra flavor.*

Let artificial intelligence take a stab at 
figuring out what your mystery tracks are all about.

---


## Who Needs This? (Definitely You)

- **You**: The person who once gazed at your MP3 folder and thought, "My beats need more AI jazz hands!"
- **Also You**: If you trust a chatbot more than your buddy Dave who keeps calling every track "Track 1".
- **Definitely You**: If you've got folders full of unlabeled files from random rips, mystery MP3s, or bootlegs you swear are real.

## Features

- **Auto-Metadata Magic**: Summon track titles, album info, and more metadata from the mysterious AI realm.
- **Cleanup Crew**: Automatically clean up your metadata mess with AI-powered suggestions. E.g. remove "Free Download" from titles, because you definitely have those files ;)


## Installation

1. **Prerequisites**: Make sure you have Beets installed (`pip install beets`), an API key for your preferred AI service, and **zero shame** about using AI.
2. **Grab the Sauce**:
   ```bash
   pip install beets-aisauce
    ```
3. **Configure the Plugin**: Add the plugin to your Beets configuration file (`config.yaml`):
    ```yaml
    plugins: 
       - aisauce

    aisauce:
        providers:
            - id: openai
              model: gpt-4o
              api_key: YOUR_API_KEY_HERE
    ```
4. Yummy sauce! You will now get AI-generated metadata suggestions for your tracks on import.

## Advanced Usage




## Contributing

Great ideas welcome! Especially if they include more puns. Open a PR or send us a message in a bottle (GitHub issues also work).

## License

This project is licensed under the MIT License—meaning you can do almost anything, but please don't sue us if the AI names your tracks "Untitled Jam 42."


## Development

The following sections are for developers who want to contribute to the project. Feel free to skip if you're just here for the AI sauce.

### Installation for Development

Clone the repository and install the package in editable mode:

```bash
git clone
pip install -e .[dev]
```

### Running Tests
To run the tests, you can use `pytest`. Make sure you have the necessary dependencies installed:

```bash
pytest .
```

### Running mypy locally

Running mypy local is a bit tricky due to the namespace packages used in this project. To run mypy, you need to specify the `--namespace-packages` and `--explicit-package-bases` flags.

```bash
mypy  --namespace-packages --explicit-package-bases .
```