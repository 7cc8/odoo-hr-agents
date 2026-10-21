"""Single place for the similarity thresholds used when matching/healing references.

IMPORTANT: these are difflib.SequenceMatcher *similarity ratios*, not calibrated
probabilities. A "0.90 confidence" means "90% of the characters line up", not
"90% chance the match is right". The values below were chosen by hand and have
never been measured against real Excel uploads; calibrate them on real mistakes
before relying on auto-repair (which stays OFF by default).

They are deliberately plain constants (no environment overrides): lowering a
safety threshold through configuration should be a reviewed code change.
"""

# Musleh: minimum overall similarity to auto-apply a patch (only when auto_repair is on).
AUTO_REPAIR_MIN_CONFIDENCE = 0.90
# Musleh: minimum similarity to PROPOSE a department/job patch.
PROPOSE_PATCH_MIN_CONFIDENCE = 0.80
# Musleh: difflib cutoff when collecting candidate references.
FUZZY_CANDIDATE_CUTOFF = 0.5
# Validator: difflib cutoff for the "closest match" hint on a rejected reference.
CLOSEST_MATCH_SUGGESTION_CUTOFF = 0.6
# Muwaffaq agent: accept / suggest / reject bands.
MUWAFFAQ_HIGH_CONFIDENCE = 0.90
MUWAFFAQ_MEDIUM_CONFIDENCE = 0.70
MUWAFFAQ_LOW_CONFIDENCE = 0.50
