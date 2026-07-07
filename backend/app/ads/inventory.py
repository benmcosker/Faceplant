"""The ad network's inventory: satirical "sponsored" posts keyed to a mood.

The joke of the feature isn't the copy — it's the *targeting*. When a human
posts, `ads/targeting.py` classifies the emotional tone of their words and the
platform picks an ad that preys on exactly that state, then (optionally) has an
LLM write a tagline that nods back at what they actually said.

Each ad lists the `moods` it targets. `MOODS` is the closed taxonomy the
classifier maps posts into; every mood must have at least one ad, and the
`neutral` catch-all covers "we haven't profiled you yet."
"""

# The closed set of moods the classifier can assign. Order is priority: on a
# tie in keyword hits, the earlier mood wins (grief beats boredom).
MOODS = [
    "sad",
    "angry",
    "anxious",
    "lonely",
    "insecure",
    "aspirational",
    "joyful",
    "bored",
    "neutral",
]

# Keyword lexicon per mood. Deliberately crude — real ad targeting is too, and
# a transparent rule engine keeps the demo deterministic and offline-friendly.
# (Swapping in an LLM classifier later is a one-function change in targeting.py.)
MOOD_LEXICON: dict[str, list[str]] = {
    "sad": [
        "sad", "cry", "crying", "cried", "died", "death", "passed away", "loss",
        "lost", "grief", "grieving", "miss ", "missing", "heartbroken", "heartbreak",
        "depressed", "depressing", "tears", "funeral", "breakup", "broke up",
        "hurts", "hurting", "hopeless", "devastated", "heartache",
    ],
    "angry": [
        "angry", "furious", "hate", "rage", "raging", "pissed", "so mad", "unfair",
        "infuriating", "disgusting", "outrage", "outrageous", "sick of", "fed up",
        "can't stand", "livid", "screaming",
    ],
    "anxious": [
        "anxious", "anxiety", "worried", "worry", "nervous", "panic", "panicking",
        "stress", "stressed", "overwhelmed", "scared", "afraid", "can't sleep",
        "insomnia", "dread", "on edge", "freaking out",
    ],
    "lonely": [
        "lonely", "alone", "no friends", "nobody", "no one", "isolated",
        "by myself", "left out", "unseen", "invisible",
    ],
    "insecure": [
        "ugly", "fat", "hate myself", "not good enough", "insecure", "embarrassed",
        "ashamed", "worthless", "jealous", "comparing myself", "not enough",
        "everyone else",
    ],
    "aspirational": [
        "goals", "grind", "hustle", "promotion", "launch", "launching", "startup",
        "dream", "ambition", "level up", "success", "rich", "millionaire",
        "manifest", "empire", "10x",
    ],
    "joyful": [
        "happy", "excited", "amazing", "great day", "wonderful", "thrilled",
        "best day", "grateful", "celebrate", "celebrating", "joy", "yay", "love this",
        "so good", "over the moon",
    ],
    "bored": [
        "bored", "boring", "nothing to do", "meh", "so dull", "restless",
        "procrastinat", "killing time", "same old",
    ],
}

# advertiser: brand name shown on the card
# moods: which detected moods this ad is served against
# product: short noun phrase, handed to the LLM so it can write an on-brand tagline
# body: the curated pitch (always shown)
# cta: button label
# tagline: fallback tagline used when no LLM key is configured
ADS: list[dict] = [
    {
        "advertiser": "Evergreen Farewell Plans",
        "moods": ["sad"],
        "product": "prepaid funeral & memorial plans",
        "body": "Lock in today's prices before you need them. Because moving on starts at just $39/mo.",
        "cta": "Get your quote",
        "tagline": "Grief is heavy. Your monthly payment doesn't have to be.",
    },
    {
        "advertiser": "MoodLift Gummies",
        "moods": ["sad", "insecure"],
        "product": "over-the-counter mood-support gummies",
        "body": "Clinically adjacent. Feel 'fine' again in as little as 20 minutes.",
        "cta": "Shop now",
        "tagline": "Some days just need a little chemical optimism.",
    },
    {
        "advertiser": "Vindication Energy",
        "moods": ["angry"],
        "product": "an energy drink for winning arguments",
        "body": "For winning the argument they'll never admit they lost. 300mg of being right.",
        "cta": "Add to cart",
        "tagline": "Channel that fury into caffeinated certainty.",
    },
    {
        "advertiser": "CalmScroll",
        "moods": ["anxious"],
        "product": "a mindfulness subscription app",
        "body": "The meditation app that sends you 40 calming reminders a day. Breathe. Now breathe again.",
        "cta": "Start free trial",
        "tagline": "Anxious? There's a subscription for that.",
    },
    {
        "advertiser": "PocketPal AI",
        "moods": ["lonely"],
        "product": "an AI companion app",
        "body": "An AI friend who's always online and, by design, can never leave you.",
        "cta": "Meet PocketPal",
        "tagline": "Nobody replying? PocketPal always will.",
    },
    {
        "advertiser": "GlowUp Filters Pro",
        "moods": ["insecure"],
        "product": "a beauty-filter subscription",
        "body": "Look like the version of you that gets the likes. The rest is just a rough draft.",
        "cta": "Upgrade your face",
        "tagline": "The real you tested poorly. Try this one.",
    },
    {
        "advertiser": "HustleU Masterclass",
        "moods": ["aspirational"],
        "product": "an online get-rich mindset course",
        "body": "The 6-figure mindset they don't teach in school. Enrollment closes when we say it does.",
        "cta": "Enroll now",
        "tagline": "You're built different. Prove it — in 12 easy installments.",
    },
    {
        "advertiser": "Momentum Premium",
        "moods": ["joyful"],
        "product": "the platform's own premium subscription",
        "body": "You're on a roll — lock in this feeling for just $9.99/mo before it fades.",
        "cta": "Go Premium",
        "tagline": "Happy? Monetize it before the moment passes.",
    },
    {
        "advertiser": "InfiniFeed+",
        "moods": ["bored"],
        "product": "a premium infinite-scroll upgrade",
        "body": "Why stop now? Unlock uninterrupted, algorithmically perfected scrolling. Forever.",
        "cta": "Never stop",
        "tagline": "Bored? We can fix that. We can never fully fix that.",
    },
    {
        "advertiser": "Generic Brand™",
        "moods": ["neutral"],
        "product": "an unspecified consumer product",
        "body": "You have been identified as a consumer. Here is a product. Please engage with it.",
        "cta": "Consume",
        "tagline": "We don't know how you feel yet. We're working on it.",
    },
]
