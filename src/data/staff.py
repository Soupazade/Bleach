STAFF_ROLE_IDS = {
    "trial_mod": 1418073228072583218,
    "mod": 1418073206337572884,
    "admin": 1418073181972861018,
    "super_admin": 1491143542075166872,
    "owner": 1418073145226694756,
}

STAFF_HIERARCHY = (
    "trial_mod",
    "mod",
    "admin",
    "super_admin",
    "owner",
)


def get_allowed_staff_role_ids(minimum_rank: str) -> set[int]:
    try:
        minimum_index = STAFF_HIERARCHY.index(minimum_rank)
    except ValueError as error:
        raise ValueError(f"Unknown staff rank: {minimum_rank}") from error

    return {
        STAFF_ROLE_IDS[rank_name]
        for rank_name in STAFF_HIERARCHY[minimum_index:]
    }
