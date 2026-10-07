"""Single source of truth for databases where mutation is permitted."""

ALLOWED_TEST_DBS = frozenset({
    "odooprosys-hr19-main-37916265",
})

# Dedicated isolated development databases (Section 1.1 of Phase 7 Plan)
ALLOWED_DEV_DBS = frozenset({
    "odooprosys-hr19-dev",
})