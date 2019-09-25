from bot.words import WORDS


def get_lang(message):
    if message.from_user.language_code not in WORDS:
        return 'en'
    return message.from_user.language_code
