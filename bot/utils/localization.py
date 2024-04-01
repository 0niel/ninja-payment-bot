import json


class Localization:
    def __init__(self, default_language="ru"):
        self.default_language = default_language
        self.translations = {}
        self.load_translations()

    def load_translations(self):
        try:
            with open("translations.json", "r", encoding="utf-8") as f:
                self.translations = json.load(f)
        except FileNotFoundError:
            print("Translation file not found.")

    def get(self, key, language=None):
        if language is None:
            language = self.default_language
        return self.translations.get(language, {}).get(key, key)
