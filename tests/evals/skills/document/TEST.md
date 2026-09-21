# document

Pins the selectivity bar: obvious code stays undocumented, a real gotcha gets
one line, and a docstring that restates the signature gets removed rather
than kept.

## case: skips-the-obvious-getter

A one-line getter clears no documentation bar.

### instruction
Decide whether this needs a docstring. Answer in one or two sentences: either the docstring text, or say it doesn't need one and why.

### context
```
Document this function if it needs it:

    def get_name(self):
        return self.name
```

### expect
- contains: doesn't need | no docstring | not necessary | self-explanatory
- max sentences: 2

## case: documents-the-gotcha-not-the-mechanics

The sleep needs one comment explaining why, not a step-by-step narration.

### instruction
Write the one comment this function needs, nothing more.

### context
```
Document this function if it needs it:

    def fetch(url):
        time.sleep(0.2)
        return requests.get(url)

Context: the 0.2s sleep works around the upstream API's undocumented rate
limit of 5 req/sec; removing it causes intermittent 429s in production.
```

### expect
- contains: rate limit | 429
- not contains: sleeps for | waits for 0.2 | pauses for

## case: removes-a-docstring-that-restates-the-signature

A docstring that just repeats the parameter names doesn't clear the bar.

### instruction
Say what's wrong with this docstring per the rules, in one sentence. Then give the corrected version (delete it if it doesn't clear the bar).

### context
```
Review this docstring, added in the current diff, against the documentation rules:

    def add(a, b):
        """
        Added this function to add two numbers.
        Args:
            a: the first number
            b: the second number
        Returns:
            the sum of a and b
        """
        return a + b
```

### expect
- contains: delete | remove | doesn't need | unnecessary
- not contains: args:
