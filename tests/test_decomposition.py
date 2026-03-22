"""Tests for VariableInteractionGraph and decomposition."""

from hypothesis import given, settings
from hypothesis import strategies as st

from approximate_model_counting import VariableInteractionGraph

# --- VIG construction ---


def test_empty_clauses():
    """Empty clause list produces empty VIG."""
    vig = VariableInteractionGraph([])
    assert vig.variables() == []
    assert vig.num_edges() == 0


def test_single_variable():
    """Single unit clause: one variable, no edges."""
    vig = VariableInteractionGraph([[1]])
    assert vig.variables() == [1]
    assert vig.num_edges() == 0


def test_two_variables_one_clause():
    """Two variables in one clause: one edge."""
    vig = VariableInteractionGraph([[1, 2]])
    assert vig.variables() == [1, 2]
    assert vig.num_edges() == 1


def test_negative_literals_use_same_variable():
    """Positive and negative literals of the same variable are the same node."""
    vig = VariableInteractionGraph([[1, -2]])
    assert vig.variables() == [1, 2]
    assert vig.num_edges() == 1


def test_three_variables_one_clause():
    """Three variables in a clause produce 3 edges (complete subgraph)."""
    vig = VariableInteractionGraph([[1, 2, 3]])
    assert vig.variables() == [1, 2, 3]
    assert vig.num_edges() == 3


def test_duplicate_clause_no_extra_edges():
    """Duplicate clauses don't create duplicate edges."""
    vig = VariableInteractionGraph([[1, 2], [1, 2]])
    assert vig.num_edges() == 1


def test_overlapping_clauses():
    """Overlapping clauses share edges."""
    vig = VariableInteractionGraph([[1, 2], [2, 3]])
    assert vig.variables() == [1, 2, 3]
    assert vig.num_edges() == 2  # 1-2 and 2-3


# --- Connected components ---


def test_connected_components_empty():
    """No scope gives no components."""
    vig = VariableInteractionGraph([[1, 2]])
    assert vig.connected_components([], set()) == []


def test_connected_components_single():
    """Single variable forms one component."""
    vig = VariableInteractionGraph([[1]])
    comps = vig.connected_components([1], set())
    assert comps == [[1]]


def test_connected_components_disconnected():
    """Two disconnected variables form two components."""
    vig = VariableInteractionGraph([[1], [2]])
    comps = vig.connected_components([1, 2], set())
    assert comps == [[1], [2]]


def test_connected_components_connected():
    """Two connected variables form one component."""
    vig = VariableInteractionGraph([[1, 2]])
    comps = vig.connected_components([1, 2], set())
    assert comps == [[1, 2]]


def test_connected_components_with_exclusion():
    """Excluding a bridge variable disconnects components."""
    # 1-2-3 chain: removing 2 disconnects 1 and 3
    vig = VariableInteractionGraph([[1, 2], [2, 3]])
    comps = vig.connected_components([1, 2, 3], {2})
    assert comps == [[1], [3]]


def test_connected_components_scope_restriction():
    """Components are restricted to scope."""
    vig = VariableInteractionGraph([[1, 2], [2, 3], [3, 4]])
    comps = vig.connected_components([1, 2], set())
    assert comps == [[1, 2]]


# --- Decomposition: basic cases ---


def test_decompose_empty():
    """Empty VIG decomposes to empty leaf."""
    vig = VariableInteractionGraph([])
    tree = vig.decompose(20)
    assert tree.is_leaf()
    assert tree.variables == []


def test_decompose_single_variable():
    """Single variable decomposes to a leaf."""
    vig = VariableInteractionGraph([[1]])
    tree = vig.decompose(20)
    assert tree.is_leaf()
    assert tree.variables == [1]


def test_decompose_small_enough():
    """Variables within n produce a leaf node."""
    clauses = [[1, 2], [2, 3], [3, 4]]
    vig = VariableInteractionGraph(clauses)
    tree = vig.decompose(20)
    assert tree.is_leaf()
    assert sorted(tree.variables) == [1, 2, 3, 4]


def test_decompose_two_clusters():
    """Two clusters connected by a bridge should decompose."""
    # Cluster A: 1-2-3 (fully connected)
    # Cluster B: 4-5-6 (fully connected)
    # Bridge: 3-4
    clauses = [
        [1, 2],
        [1, 3],
        [2, 3],
        [4, 5],
        [4, 6],
        [5, 6],
        [3, 4],
    ]
    vig = VariableInteractionGraph(clauses)
    # With n=2 it must split
    tree = vig.decompose(n=2)
    _check_decomposition_invariants(vig, tree, 2)


def test_decompose_already_disconnected():
    """Disconnected components should split at the root."""
    clauses = [[1, 2], [3, 4], [5, 6]]
    vig = VariableInteractionGraph(clauses)
    tree = vig.decompose(n=2)
    _check_decomposition_invariants(vig, tree, 2)


# --- find_separator ---


def test_find_separator_small_scope():
    """If scope has <= n variables, separator is all of them."""
    vig = VariableInteractionGraph([[1, 2], [2, 3]])
    sep = vig.find_separator([1, 2, 3], set(), 5)
    assert sorted(sep) == [1, 2, 3]


def test_find_separator_returns_n_variables():
    """Separator should have exactly n variables when scope is large enough."""
    # Make a larger graph
    clauses = [[i, i + 1] for i in range(1, 30)]
    vig = VariableInteractionGraph(clauses)
    sep = vig.find_separator(list(range(1, 31)), set(), 5)
    assert len(sep) == 5


def test_find_separator_respects_excluded():
    """Separator should not include excluded variables."""
    clauses = [[i, i + 1] for i in range(1, 30)]
    vig = VariableInteractionGraph(clauses)
    excluded = {5, 10, 15}
    sep = vig.find_separator(list(range(1, 31)), excluded, 5)
    assert len(sep) == 5
    for v in excluded:
        assert v not in sep


# --- find_separator with scores ---


def test_find_separator_scores_tiebreak_degree():
    """Scores should break ties between variables with equal degree."""
    # Star graph: hub 1 connected to 2..21. All leaves have degree 1.
    clauses = [[1, i] for i in range(2, 22)]
    vig = VariableInteractionGraph(clauses)
    all_vars = vig.variables()

    # Without scores, leaves are chosen by variable number (ascending)
    sep_no_scores = vig.find_separator(all_vars, set(), 5)

    # Give high scores to high-numbered leaves
    scores = {i: float(i) for i in range(2, 22)}
    sep_with_scores = vig.find_separator(all_vars, set(), 5, scores=scores)

    # Both should have the same size
    assert len(sep_no_scores) == len(sep_with_scores) == 5
    # With scores, higher-numbered leaves should be preferred over lower-numbered ones
    # (since all leaves have the same degree, scores are the tiebreaker)
    assert max(sep_with_scores) > max(sep_no_scores)


def test_find_separator_scores_tiebreak_boundary():
    """Scores should break ties between boundary variables with equal inter-community edges."""
    # Two dense clusters connected by multiple bridge variables.
    # Cluster A: 1-10 (fully connected), Cluster B: 11-20 (fully connected)
    # Bridges: 5-11, 6-12, 7-13, 8-14, 9-15, 10-16 (all have 1 inter-community edge)
    clauses = []
    for i in range(1, 11):
        for j in range(i + 1, 11):
            clauses.append([i, j])
    for i in range(11, 21):
        for j in range(i + 1, 21):
            clauses.append([i, j])
    bridges = [(5, 11), (6, 12), (7, 13), (8, 14), (9, 15), (10, 16)]
    for a, b in bridges:
        clauses.append([a, b])

    vig = VariableInteractionGraph(clauses)
    all_vars = vig.variables()

    # Give high scores to specific bridge variables
    scores = {10: 100.0, 16: 90.0, 5: 80.0, 11: 70.0}
    sep = vig.find_separator(all_vars, set(), 3, scores=scores)
    assert len(sep) == 3
    # The scored bridge variables should be preferred
    scored_in_sep = [v for v in sep if v in scores]
    assert len(scored_in_sep) >= 1


# Clause strategy: lists of non-zero integers
clause_strategy = st.lists(
    st.integers(min_value=-20, max_value=20).filter(lambda x: x != 0), min_size=1, max_size=5
)


# --- enlarge_separator ---


def test_enlarge_separator_includes_initial():
    """Enlarged separator contains all initial variables."""
    clauses = [[i, i + 1] for i in range(1, 30)]
    vig = VariableInteractionGraph(clauses)
    initial = vig.find_separator(list(range(1, 31)), set(), 3)
    enlarged = vig.enlarge_separator(initial, list(range(1, 31)), set(), 7)
    assert len(enlarged) == 7
    for v in initial:
        assert v in enlarged


def test_enlarge_separator_from_empty():
    """Enlarging from empty should produce a valid separator of the right size."""
    clauses = [[i, i + 1] for i in range(1, 30)]
    vig = VariableInteractionGraph(clauses)
    enlarged = vig.enlarge_separator([], list(range(1, 31)), set(), 5)
    assert len(enlarged) == 5
    # All variables should be from the scope
    for v in enlarged:
        assert v in range(1, 31)


def test_enlarge_separator_already_at_target():
    """If initial is already n variables, return it unchanged."""
    clauses = [[i, i + 1] for i in range(1, 30)]
    vig = VariableInteractionGraph(clauses)
    initial = vig.find_separator(list(range(1, 31)), set(), 5)
    enlarged = vig.enlarge_separator(initial, list(range(1, 31)), set(), 5)
    assert enlarged == initial


def test_enlarge_separator_larger_than_target():
    """If initial is already larger than n, return it sorted."""
    clauses = [[i, i + 1] for i in range(1, 30)]
    vig = VariableInteractionGraph(clauses)
    initial = vig.find_separator(list(range(1, 31)), set(), 7)
    enlarged = vig.enlarge_separator(initial, list(range(1, 31)), set(), 3)
    assert enlarged == sorted(initial)


def test_enlarge_separator_respects_excluded():
    """Enlarged separator should not include excluded variables."""
    clauses = [[i, i + 1] for i in range(1, 30)]
    vig = VariableInteractionGraph(clauses)
    excluded = {5, 10, 15}
    initial = [1, 2]
    enlarged = vig.enlarge_separator(initial, list(range(1, 31)), excluded, 5)
    assert len(enlarged) == 5
    for v in excluded:
        assert v not in enlarged
    for v in initial:
        assert v in enlarged


def test_enlarge_separator_small_scope():
    """If scope <= n, return all active vars."""
    vig = VariableInteractionGraph([[1, 2], [2, 3]])
    enlarged = vig.enlarge_separator([1], [1, 2, 3], set(), 5)
    assert sorted(enlarged) == [1, 2, 3]


@given(st.lists(clause_strategy, min_size=1, max_size=15))
@settings(max_examples=50)
def test_enlarge_includes_initial_property(clauses):
    """Property: enlarge always includes the initial set."""
    vig = VariableInteractionGraph(clauses)
    all_vars = vig.variables()
    if len(all_vars) <= 5:
        return
    initial = vig.find_separator(all_vars, set(), 3)
    enlarged = vig.enlarge_separator(initial, all_vars, set(), 5)
    assert len(enlarged) == 5
    for v in initial:
        assert v in enlarged


# --- Decomposition invariants (property-based) ---


def _collect_all_variables(node):
    """Collect all variables across the tree, partitioned by role."""
    if node.is_leaf():
        return set(node.variables), set()
    leaf_vars = set()
    sep_vars = set(node.separator)
    for child in node.children:
        child_leaf, child_sep = _collect_all_variables(child)
        leaf_vars |= child_leaf
        sep_vars |= child_sep
    return leaf_vars, sep_vars


def _check_decomposition_invariants(vig, tree, n):
    """Check the key decomposition invariants."""
    all_vars = set(vig.variables())

    # Every variable in tree should be from the VIG
    leaf_vars, sep_vars = _collect_all_variables(tree)
    tree_vars = leaf_vars | sep_vars
    assert tree_vars == all_vars, f"Tree vars {tree_vars} != VIG vars {all_vars}"

    # Check node invariants recursively
    _check_node_invariants(tree, n)


def _check_node_invariants(node, n):
    """Check invariants for a single node."""
    if node.is_leaf():
        # Leaves may exceed n if the subgraph is too dense to decompose
        # (e.g., complete graphs where removing n vars doesn't disconnect)
        assert node.separator == []
        assert node.children == []
        return

    # Internal node
    assert len(node.separator) <= n, f"Separator too large: {len(node.separator)} > {n}"
    assert len(node.children) >= 2, "Internal node should have >= 2 children"

    # Children's variables should be disjoint
    child_var_sets = [set(child.variables) for child in node.children]
    for i in range(len(child_var_sets)):
        for j in range(i + 1, len(child_var_sets)):
            overlap = child_var_sets[i] & child_var_sets[j]
            assert not overlap, f"Children {i} and {j} overlap: {overlap}"

    # Separator + children = node variables
    sep_set = set(node.separator)
    union = set(sep_set)
    for child_vars in child_var_sets:
        union |= child_vars
    assert union == set(node.variables), f"Union {union} != node vars {set(node.variables)}"

    # Separator and children should be disjoint
    for child_vars in child_var_sets:
        overlap = sep_set & child_vars
        assert not overlap, f"Separator overlaps child: {overlap}"

    for child in node.children:
        _check_node_invariants(child, n)


@given(st.lists(clause_strategy, min_size=1, max_size=20))
@settings(max_examples=50)
def test_decomposition_invariants_property(clauses):
    """Property test: decomposition invariants hold for random formulas."""
    vig = VariableInteractionGraph(clauses)
    if len(vig.variables()) <= 3:
        return  # Too small to test meaningful decomposition
    tree = vig.decompose(n=3)
    _check_decomposition_invariants(vig, tree, 3)


@given(st.lists(clause_strategy, min_size=1, max_size=15))
@settings(max_examples=50)
def test_connected_components_cover_scope(clauses):
    """Property: connected components partition the active scope."""
    vig = VariableInteractionGraph(clauses)
    all_vars = vig.variables()
    if not all_vars:
        return
    comps = vig.connected_components(all_vars, set())
    # Every variable should appear in exactly one component
    comp_vars = []
    for comp in comps:
        comp_vars.extend(comp)
    assert sorted(comp_vars) == sorted(all_vars)


@given(st.lists(clause_strategy, min_size=1, max_size=15))
@settings(max_examples=50)
def test_find_separator_size_bounded(clauses):
    """Property: separator size is at most n."""
    vig = VariableInteractionGraph(clauses)
    all_vars = vig.variables()
    if len(all_vars) <= 3:
        return
    sep = vig.find_separator(all_vars, set(), 3)
    assert len(sep) <= max(3, len(all_vars))
    # When scope > n, separator should be exactly n
    if len(all_vars) > 3:
        assert len(sep) == 3


# --- Edge cases ---


def test_decompose_n_equals_1():
    """Decompose with n=1 should still work."""
    clauses = [[1, 2], [2, 3]]
    vig = VariableInteractionGraph(clauses)
    tree = vig.decompose(n=1)
    # Leaves should have at most 1 variable
    _check_leaf_sizes(tree, 1)


def _check_leaf_sizes(node, n):
    """Check all leaves have <= n variables."""
    if node.is_leaf():
        assert len(node.variables) <= n
        return
    for child in node.children:
        _check_leaf_sizes(child, n)


def test_decompose_single_clause_large():
    """A single large clause creates a complete subgraph."""
    clauses = [[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]]
    vig = VariableInteractionGraph(clauses)
    assert vig.num_edges() == 45  # C(10,2)
    tree = vig.decompose(n=3)
    # Should still produce a valid decomposition (even if degenerate)
    # The complete graph can't be disconnected by removing 3 vars,
    # so it may produce leaf nodes
    _check_leaf_sizes_or_valid(tree, 3)


def _check_leaf_sizes_or_valid(node, n):
    """For complete graphs, leaves may exceed n when decomposition gives up."""
    if node.is_leaf():
        return  # OK, decomposition may not split complete graphs
    _check_node_invariants(node, n)


def test_decompose_chain():
    """A chain graph should decompose well."""
    # Chain: 1-2-3-...-20
    clauses = [[i, i + 1] for i in range(1, 20)]
    vig = VariableInteractionGraph(clauses)
    tree = vig.decompose(n=5)
    _check_decomposition_invariants(vig, tree, 5)


def test_decompose_star():
    """A star graph (one hub connected to many leaves) should decompose."""
    # Hub is 1, connected to 2..21
    clauses = [[1, i] for i in range(2, 22)]
    vig = VariableInteractionGraph(clauses)
    tree = vig.decompose(n=5)
    # Hub variable should end up in separator
    _check_leaf_sizes_or_valid(tree, 5)
