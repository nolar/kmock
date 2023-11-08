# AI-generated. The algorithm is NOT a focus or a feature of this library.
# We do not care about the quality or efficiency of the algorithm much,
# as long as it provides realistic matches of objects & patterns.
# It is usually used with only a few hard-coded patterns anyway.
# The tests are here as a smoke detector, "just in case".
from kmock._internal.k8s_views import _match_objects_to_patterns


def test_empty_input():
    """Test with empty matches dictionary."""
    matches = {}
    source_to_target, target_to_source = _match_objects_to_patterns(matches)

    assert source_to_target == {}
    assert target_to_source == {}


def test_single_match():
    """Test with a single source-target pair."""
    matches = {0: {0}}
    source_to_target, target_to_source = _match_objects_to_patterns(matches)

    assert source_to_target == {0: 0}
    assert target_to_source == {0: 0}


def test_perfect_matching():
    """Test where all sources can be matched to unique targets."""
    matches = {
        0: {0},
        1: {1},
        2: {2}
    }
    source_to_target, target_to_source = _match_objects_to_patterns(matches)

    assert source_to_target == {0: 0, 1: 1, 2: 2}
    assert target_to_source == {0: 0, 1: 1, 2: 2}


def test_multiple_candidates_per_source():
    """Test where sources have multiple possible targets."""
    matches = {
        0: {0, 1, 2},
        1: {1, 2},
        2: {2}
    }
    source_to_target, target_to_source = _match_objects_to_patterns(matches)

    # Verify all sources are matched
    assert len(source_to_target) == 3
    assert len(target_to_source) == 3

    # Verify one-to-one correspondence
    assert set(source_to_target.keys()) == {0, 1, 2}
    assert set(target_to_source.keys()) == {0, 1, 2}

    # Verify consistency
    for src, tgt in source_to_target.items():
        assert target_to_source[tgt] == src


def test_conflict_resolution():
    """Test where multiple sources compete for the same target."""
    matches = {
        0: {0},
        1: {0}
    }
    source_to_target, target_to_source = _match_objects_to_patterns(matches)

    # Only one source can be matched
    assert len(source_to_target) == 1
    assert len(target_to_source) == 1

    # Either source 0 or 1 should be matched to target 0
    assert source_to_target.get(0) == 0 or source_to_target.get(1) == 0
    assert target_to_source[0] in {0, 1}


def test_augmenting_path_scenario():
    """Test a scenario that requires finding an augmenting path."""
    matches = {
        0: {0, 1},
        1: {1},
        2: {0}
    }
    source_to_target, target_to_source = _match_objects_to_patterns(matches)

    # All three sources should be matched
    assert len(source_to_target) == 2
    assert len(target_to_source) == 2

    # Verify no overlaps
    assert len(set(source_to_target.values())) == len(source_to_target)

    # Verify bidirectional consistency
    for src, tgt in source_to_target.items():
        assert target_to_source[tgt] == src

    # Both targets should be matched
    assert set(target_to_source.keys()) == {0, 1}


def test_unmatched_sources():
    """Test where some sources cannot be matched."""
    matches = {
        0: {0},
        1: {0},
        2: {0}
    }
    source_to_target, target_to_source = _match_objects_to_patterns(matches)

    # Only one source can be matched to target 0
    assert len(source_to_target) == 1
    assert len(target_to_source) == 1
    assert 0 in target_to_source


def test_source_with_no_targets():
    """Test where a source has an empty set of targets."""
    matches = {
        0: set(),
        1: {1}
    }
    source_to_target, target_to_source = _match_objects_to_patterns(matches)

    assert 0 not in source_to_target
    assert source_to_target == {1: 1}
    assert target_to_source == {1: 1}


def test_bidirectional_consistency():
    """Test that source_to_target and target_to_source are inverse mappings."""
    matches = {
        0: {1, 2, 3},
        1: {0, 2},
        2: {1, 3},
        3: {0, 3}
    }
    source_to_target, target_to_source = _match_objects_to_patterns(matches)

    # Verify inverse relationship
    for src, tgt in source_to_target.items():
        assert target_to_source[tgt] == src

    for tgt, src in target_to_source.items():
        assert source_to_target[src] == tgt


def test_no_overlap_in_matches():
    """Test that no target is matched to multiple sources."""
    matches = {
        0: {0, 1},
        1: {1, 2},
        2: {2, 3},
        3: {3, 4}
    }
    source_to_target, target_to_source = _match_objects_to_patterns(matches)

    # All targets should be unique
    matched_targets = list(source_to_target.values())
    assert len(matched_targets) == len(set(matched_targets))

    # All sources should be unique
    matched_sources = list(target_to_source.values())
    assert len(matched_sources) == len(set(matched_sources))


def test_complex_graph():
    """Test a complex bipartite graph requiring multiple augmentations."""
    matches = {
        0: {0, 1},
        1: {1, 2},
        2: {0, 2},
        3: {3},
        4: {3, 4}
    }
    source_to_target, target_to_source = _match_objects_to_patterns(matches)

    # Maximum matching should be 5 (all sources matched)
    assert len(source_to_target) == 5
    assert len(target_to_source) == 5

    # Verify all constraints
    for src, tgt in source_to_target.items():
        assert tgt in matches[src]
        assert target_to_source[tgt] == src


def test_disjoint_components():
    """Test graph with multiple disconnected components."""
    matches = {
        0: {0, 1},
        1: {1},
        5: {5, 6},
        6: {6}
    }
    source_to_target, target_to_source = _match_objects_to_patterns(matches)

    # All sources should be matched
    assert len(source_to_target) == 4
    assert len(target_to_source) == 4

    # Verify matches respect the input constraints
    for src, tgt in source_to_target.items():
        assert tgt in matches[src]


def test_large_candidate_set():
    """Test with a large number of candidates per source."""
    matches = {
        0: set(range(100)),
        1: set(range(50, 150)),
        2: set(range(100, 200))
    }
    source_to_target, target_to_source = _match_objects_to_patterns(matches)

    # All sources should be matched
    assert len(source_to_target) == 3
    assert len(target_to_source) == 3

    # Verify no overlaps
    targets = set(source_to_target.values())
    assert len(targets) == 3


def test_negative_indices():
    """Test with negative indices."""
    matches = {
        -1: {-10, -20},
        -2: {-20, -30},
        -3: {-30}
    }
    source_to_target, target_to_source = _match_objects_to_patterns(matches)

    assert len(source_to_target) == 3
    assert len(target_to_source) == 3

    for src, tgt in source_to_target.items():
        assert tgt in matches[src]


def test_matching_quality():
    """Test that matching produces maximum cardinality."""
    matches = {
        0: {0},
        1: {0, 1},
        2: {1, 2},
        3: {2}
    }
    source_to_target, target_to_source = _match_objects_to_patterns(matches)

    # Maximum matching with 4 sources and 3 targets = 3 matches
    assert len(source_to_target) == 3
    assert len(target_to_source) == 3

    # All targets should be used (maximum cardinality)
    assert set(target_to_source.keys()) == {0, 1, 2}

    # One source will be unmatched
    assert len({0, 1, 2, 3} - set(source_to_target.keys())) == 1

    # Verify consistency
    for src, tgt in source_to_target.items():
        assert tgt in matches[src]
        assert target_to_source[tgt] == src


def test_deterministic_behavior():
    """Test that the function produces consistent results for the same input."""
    matches = {
        0: {0, 1, 2},
        1: {1, 2, 3},
        2: {2, 3, 4}
    }

    # Run multiple times
    results = [_match_objects_to_patterns(matches) for _ in range(5)]

    # All results should have the same cardinality
    cardinalities = [len(result[0]) for result in results]
    assert len(set(cardinalities)) == 1  # All the same

    # All should be maximum matching
    assert cardinalities[0] == 3


def test_loops_impossible():
    """Test behavior when source and target indices overlap (bipartite assumption)."""
    matches = {
        0: {0, 1},
        1: {0, 1}
    }
    source_to_target, target_to_source = _match_objects_to_patterns(matches)

    # Both should be matched (2 sources, 2 targets available)
    assert len(source_to_target) == 2
    assert len(target_to_source) == 2


def test_sparse_indices():
    """Test with non-contiguous indices."""
    matches = {
        100: {500, 501},
        200: {501, 502},
        300: {502}
    }
    source_to_target, target_to_source = _match_objects_to_patterns(matches)

    assert len(source_to_target) == 3
    assert set(source_to_target.keys()) == {100, 200, 300}


def test_single_target_many_sources():
    """Test bottleneck scenario with many sources competing for one target."""
    matches = {i: {0} for i in range(10)}
    source_to_target, target_to_source = _match_objects_to_patterns(matches)

    # Only one source can win
    assert len(source_to_target) == 1
    assert len(target_to_source) == 1
    assert target_to_source[0] in range(10)


def test_many_targets_single_source():
    """Test scenario with one source but many targets."""
    matches = {0: set(range(100))}
    source_to_target, target_to_source = _match_objects_to_patterns(matches)

    # Source should be matched to one of the targets
    assert len(source_to_target) == 1
    assert len(target_to_source) == 1
    assert 0 in source_to_target
    assert source_to_target[0] in range(100)
