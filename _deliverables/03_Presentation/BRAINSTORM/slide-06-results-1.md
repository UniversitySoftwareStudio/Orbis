# Slide 6 — Results & Testing 1/2: search + rules + matching (Atakan, ~70s)

**Goal:** Start with strong search numbers, then rule-pulling, then say plainly that matching is the weak part.

## Say
- "We tested every part against a hand-checked answer set. Start with the chatbot."
- "On **100 questions** in Turkish and English, across 7 types: **92.3% correct routing, 94.7% found the right source, 0.94 MRR, 97.6% correct answers.**"
- "Our model choice is backed by a smaller test — MiniLM with 100-word chunks gave the best results."
- "Rule-pulling: from 80 sources in 59 minutes, we checked 323 candidates and kept 178."
- "Against the answer set that's **97.8% precision** — very strict, only 4 wrong accepts. Recall is 57%, which is the price of being strict."
- "Now the honest part: **matching is our weakest part — F1 of 0.51.** It assigns broad rules too widely and misses some personal ones. We know why, and it's on the roadmap."

## Show / point at
- Show the chatbot card first. Then the rule-pulling card with its table. Then the matching card — point to the red mark on the weak spot.

## Transition out
- "The submission checker is our strongest safety story — next slide." → stay on (Atakan goes to slide 7).

## If asked
- "Why high precision but low recall?" → "On purpose. A wrong obligation hurts trust more than a missed one, so we tuned for precision."
- "Why is matching weak?" → "Two reasons: broad rules like 'submit graduation poster' get sent to everyone, and personal rules sometimes don't fire. A second recall pass is the fix."
- "Is letting an AI judge fair?" → "We double-check the judge with a second model from a different maker, and humans built the answer set."

## Don't
- Don't hide the matching weakness. Say it clearly — the report already does.
- Don't read every cell of the table. Point to it, say the headline number.
