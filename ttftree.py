"""
Experimental implementation of functional 2-3 finger trees that I'm working on.

I'm hoping to replace stm.avl with these, which'll give O(1) list insertion,
appending, and removal from either end to stm.tlist.TList.

I'm also planning on implementing custom measures (which could also be done
with stm.avl), which'll give the ability for, e.g., an ordered list to also
function as a priority queue.
"""

# Credit goes to http://maniagnosis.crsr.net/2010/11/finger-trees.html for
# giving my brain just the right information it needed to finally understand
# 2-3 finger trees 

from collections import Sequence

class TTFTreeError(Exception):
    pass


class TreeIsEmpty(TTFTreeError):
    """
    Exception raised from within Empty when things like get_first or
    without_first are called on it.
    """
    def __str__(self):
        return "This tree is empty"


class Identity(object):
    pass


IDENTITY = Identity()


class Measure(object):
    """
    An object used to compute a tree's annotation.
    
    Measures consist of a function capable of converting values in a tree to
    values in a particular monoid (the convert attribute of Measure objects)
    and the monoid's binary operation (the operator attribute) and identity
    element (the identity attribute). The value of any given tree is the
    monoidal sum of the values produced by the conversion function for all
    values contained within the tree.
    """
    def convert(self, value):
        """
        Converts a value stored in a tree to a value in the monoid on which
        this measure operates. This will be called for each value added to a
        tree using this measure, and only values returned from this function
        (as well as self.identity) will be passed to self.operator().
        
        The default implementation raises NotImplementedError.
        """
        raise NotImplementedError
    
    def operator(self, a, b):
        """
        Take two values returned from self.convert() (or possibly
        self.identity) and combine them according to whatever logic this
        measure deems appropriate.
        
        This is the sum operator of the monoid under which this measure
        operates. As such, when passed self.identity as either of its
        arguments, it must return the other argument without any changes.
        
        The default implementation raises NotImplementedError.
        """
        raise NotImplementedError
    

class CustomMeasure(Measure):
    """
    A class for creating custom measures when one would rather just pass in the
    convert, operator, and identity functions instead of creating a subclass of
    Measure.
    """
    def __init__(self, convert, operator, identity):
        self.convert = convert
        self.operator = operator
        self.identity = identity
    
    def __repr__(self):
        return "<CustomMeasure: convert=%r, operator=%r, identity=%r>" % (self.convert, self.operator, self.identity)


class MeasureItemCount(Measure):
    """
    A measure that measures the number of items contained within a given tree.
    
    Trees annotated with such a measure can be asked for the number of items
    that they contain in O(1) time by simply referencing the tree's annotation:
    
        tree_size = some_tree.annotation
    
    They can also be asked to produce their nth item in O(log n) time:
    
        left, right = some_tree.partition(lambda v: v > n)
        nth_value = right.get_first()
    
    A value can be inserted just before their nth item in O(log n) time:
    
        left, right = some_tree.partition(lambda v: v > n)
        some_tree = left.add_last(value_to_insert).append(right)
    
    The value at the nth position in the tree can be removed in O(log n) time:
    
        left, right = some_tree.partition(lambda v: v > n)
        some_tree = left.append(right.without_first())
    
    A subtree consisting of the mth (inclusive) through nth (exclusive) values
    can be constructed in O(log n) time:
    
        mid, right = some_tree.partition(lambda v: v > n)
        left, mid = mid.partition(lambda v: v > m)
        subtree = mid
    
    And finally, the mth (inclusive) through nth (exclusive) values can be
    removed in O(log n) time:
    
        mid, right = some_tree.partition(lambda v: v > n)
        left, mid = mid.partition(lambda v: v > m)
        some_tree = left.append(right)
    
    A singleton instance of this class is stored in ttftree.MEASURE_ITEM_COUNT.
    You'll typically want to use that constant instead of constructing a whole
    new instance of MeasureItemCount.
    """
    def __init__(self):
        Measure.__init__(self)
        self.identity = 0
    
    def convert(self, value):
        return 1
    
    def operator(self, a, b):
        return a + b


class MeasureWithIdentity(Measure):
    """
    An abstract subclass of Measure that uses ttftree.IDENTITY as the identity
    element and automatically handles checking for IDENTITY in its
    implementation of operator(). It thus allows a semigroup (such as the set
    of comparable objects under the min or max functions) to be used as a
    monoid and therefore as a measure.
    
    Subclasses must override convert and semigroup_operator. They must not
    change self.identity or override operator.
    """
    def __init__(self):
        Measure.__init__(self)
        self.identity = IDENTITY
    
    def operator(self, a, b):
        if a is IDENTITY:
            return b
        elif b is IDENTITY:
            return a
        else:
            return self.semigroup_operator(a, b)
    
    def semigroup_operator(self, a, b):
        raise NotImplementedError

    
class MeasureLastItem(MeasureWithIdentity):
    """
    A measure that simply produces the second of the two items it's passed.
    """
    def convert(self, value):
        return value
    
    def semigroup_operator(self, a, b):
        return b


class MeasureMinMax(MeasureWithIdentity):
    def convert(self, value):
        return value
    
    def operator(self, a, b):
            a_min, a_max = a
            b_min, b_max = b
            return min(a_min, b_min), max(a_max, b_max)


class TranslateMeasure(Measure):
    """
    A measure that wraps another measure and behaves identically to it except
    that it passes all values passed to self.convert() into the specified
    function and passes the result into the wrapped measure's convert().
    
    This can be used to, for example, create a wrapper around MeasureMinMax
    that compares a certain attribute of its values instead of the values
    themselves. For example, consider a tree with objects that have a
    "priority" attribute. A measure suitable for using this tree as a priority
    queue based on this attribute could be constructed thus:
    
    measure = TranslateMeasure(lambda v: v.priority, MeasureMinMax())
    """
    def __init__(self, function, measure):
        Measure.__init__(self)
        self._function = function
        self._wrapped_convert = measure.convert
        self.operator = measure.operator
        self.identity = measure.identity
    
    def convert(self, value):
        return self._wrapped_convert(self._function(value))


class CompoundMeasure(Measure):
    """
    A measure that combines the specified measures and produces a tuple of
    their computed values. It can be used to annotate a tree with multiple
    measures at the same time.
    """
    def __init__(self, *measures):
        self.measures = measures
        self.identity = tuple(m.identity for m in self.measures)
    
    def convert(self, value):
        return tuple(m.convert(value) for m in self.measures)
    
    def operator(self, a_values, b_values):
        return tuple(m.operator(a, b) for (m, a, b) in zip(self.measures, a_values, b_values))


class _NodeMeasure(Measure):
    def __init__(self, measure):
        self.convert = self.convert
        self.operator = measure.operator
        self.identity = measure.identity
    
    def convert(self, node):
        return node.annotation


MEASURE_ITEM_COUNT = MeasureItemCount()


class Node(Sequence):
    def __init__(self, measure, *values):
        if len(values) not in (2, 3):
            raise Exception("Nodes must have 2 or 3 children")
        self._values = values
        self.measure = measure
        self.annotation = reduce(measure.operator, map(measure.convert, values))
    
    def __getitem__(self, index):
        if isinstance(index, slice):
            return Node(self.measure, *self._values[index])
        else:
            return self._values[index]
    
    def __len__(self):
        return len(self._values)
    
    def __add__(self, other):
        return Node(self.measure, *self._values + other._values)
    
    def __repr__(self):
        return "<Node: %s>" % ", ".join([repr(v) for v in self])


class Digit(Sequence):
    def __init__(self, measure, *values):
        if len(values) not in (1, 2, 3, 4):
            raise Exception("Digits must have 1, 2, 3, or 4 children; the "
                            "children given were %r" % list(values))
        self._values = values
        self.measure = measure
        self.annotation = reduce(measure.operator, map(measure.convert, values))
    
    def partition_digit(self, initial_annotation, predicate):
        """
        partition_digit(function) => ((...), (...))
        
        Note that the two return values are tuples, not Digits, as they may
        need to be empty.
        """
        split_point = 0
        while split_point < len(self):
            current_annotation = self.measure.operator(initial_annotation, self.measure.convert(self[split_point]))
            if predicate(current_annotation):
                break
            else:
                split_point += 1
                initial_annotation = current_annotation
        return self._values[:split_point], self._values[split_point:]
    
    def __getitem__(self, index):
        if isinstance(index, slice):
            return Digit(self.measure, *self._values[index])
        else:
            return self._values[index]
    
    def __len__(self):
        return len(self._values)
    
    def __add__(self, other):
        return Digit(self.measure, *self._values + other._values)
    
    def __repr__(self):
        return "<Digit: %s>" % ", ".join([repr(v) for v in self])


class Tree(object):
    """
    A class representing a 2-3 finger tree.
    
    Tree is an abstract class, so it can't itself be instantiated. Instead,
    you'll want to construct an instance of Empty, one of the three subclasses
    of Tree needed for the 2-3 finger tree algorithm (the other two are Single
    and Deep), then add items to it as necessary.
    
    A convenience function, to_tree, is provided to convert any Python sequence
    into a Tree instance. 
    """
    # is_empty -> bool
    
    # get_first() -> item
    # without_first() -> Tree
    # add_first(item) -> Tree
    # get_last() -> item
    # without_last() -> Tree
    # add_last(item) -> Tree
    
    # append(tree) -> Tree
    # prepend(tree) -> Tree
    def partition(self, predicate):
        """
        Convenience function that simply returns
        self.partition_with(predicate, self.measure.identity).
        """
        return self.partition_with(predicate, self.measure.identity)
    
    def __add__(self, other):
        """
        A wrapper that simply returns self.append(other) unless other is not an
        instance of Tree, in which case  NotImplemented is returned.
        """
        if not isinstance(other, Tree):
            return NotImplemented
        return self.append(other)
    
    def __radd__(self, other):
        """
        A wrapper that simply returns self.prepend(other) unless other is not
        an instance of Tree, in which case NotImplemented is returned.
        """
        if not isinstance(other, Tree):
            return NotImplemented
        return self.prepend(other)


def to_tree(measure, sequence):
    """
    Converts a given Python sequence (list, iterator, or anything else that
    can be the target of a for loop) into a Tree instance.
    
    This just creates an Empty instance and adds items to it with its add_last
    function, taking advantage of the fact that add_last runs in amortized
    O(1) time. The time complexity of to_tree is therefore O(n).
    """
    tree = Empty(measure)
    for value in sequence:
        tree = tree.add_last(value)
    return tree


class Empty(Tree):
    """
    A subclass of Tree representing the empty tree.
    """
    is_empty = True
    
    def __init__(self, measure):
        self.measure = measure
        self.annotation = measure.identity
    
    def get_first(self):
        raise TreeIsEmpty
    
    def without_first(self):
        raise TreeIsEmpty
    
    def add_first(self, item):
        return Single(self.measure, item)
    
    def get_last(self):
        raise TreeIsEmpty
    
    def without_last(self):
        raise TreeIsEmpty
    
    def add_last(self, item):
        return Single(self.measure, item)
    
    def prepend(self, other):
        return other
    
    def append(self, other):
        return other
    
    def iterate_values(self):
        if False:
            yield None
    
    def partition_with(self, predicate, initial_annotation):
        return self, self
    
    def __repr__(self):
        return "<Empty>"


class Single(Tree):
    """
    A subclass of Tree representing trees containing a single value.
    
    Instances of Single simply store a reference to the item passed to them.
    """
    is_empty = False
    
    def __init__(self, measure, item):
        self.measure = measure
        self.annotation = measure.convert(item)
        self.item = item
    
    def get_first(self):
        return self.item
    
    def without_first(self):
        return Empty(self.measure)
    
    def add_first(self, new_item):
        return Deep(self.measure, Digit(self.measure, new_item), Empty(_NodeMeasure(self.measure)), Digit(self.measure, self.item))
    
    def get_last(self):
        return self.item
    
    def without_last(self):
        return Empty(self.measure)
    
    def add_last(self, new_item):
        return Deep(self.measure, Digit(self.measure, self.item), Empty(_NodeMeasure(self.measure)), Digit(self.measure, new_item))
    
    def prepend(self, other):
        return other.add_last(self.item)
    
    def append(self, other):
        return other.add_first(self.item)
    
    def iterate_values(self):
        yield self.item
    
    def partition_with(self, predicate, initial_annotation):
        if predicate(self.measure.operator(initial_annotation, self.annotation)):
            return Empty(self.measure), self
        else:
            return self, Empty(self.measure)
    
    def __repr__(self):
        return "<Single: %r>" % (self.item,)


def deep_left(measure, maybe_left, spine, right):
    """
    Same as Deep(measure, maybe_left, spine, right), except that maybe_left can
    be a list and is permitted to contain no items at all. In such a case, a
    node will be popped off of the spine and used as the left digit, with
    to_tree(right) being returned if the spine is actually empty.
    """
    if not maybe_left:
        if spine.is_empty:
            return to_tree(measure, right)
        else:
            return Deep(measure, Digit(measure, *spine.get_first()), spine.without_first(), right)
    else:
        return Deep(measure, Digit(measure, *maybe_left), spine, right)


def deep_right(measure, left, spine, maybe_right):
    """
    Symmetrical operation to deep_left that allows its right digit to be a list
    that's potentially empty.
    """
    if not maybe_right:
        if spine.is_empty:
            return to_tree(measure, left)
        else:
            return Deep(measure, left, spine.without_last(), Digit(measure, *spine.get_last()))
    else:
        return Deep(measure, left, spine, Digit(measure, *maybe_right))


class Deep(Tree):
    """
    A subclass of Tree representing trees containing two or more values.
    
    Deep instances store two buffers (instances of Digit) representing their
    first and last 1, 2, 3, or 4 values, and another Tree instance storing
    groups (specifically Node instances) of all of the values in between.
    
    Values added to a Deep instance with add_first and add_last are initially
    stored in their respective Digit; when the digit becomes full, items are
    popped off of it and turned into a Node, then pushed onto the nested tree.
    This is where 2-3 finger trees get their amortized constant time complexity
    for deque operations: because of the Digit buffers at either end and
    because Nodes can contain only 2 or 3 items, a call to add_first or
    add_last can descend into the nested tree at most every other call, and by
    extension can only descend one more level every /fourth/ call, and so on.
    
    Removal is accomplished the same way: if the Digit buffer on the side from
    which an item is to be removed has only one item, a Node instance is popped
    off of the nested tree and expanded into the Digit buffer. Thus the same
    amortized constant time performance guarantees apply to without_first and
    without_last as well.
    """
    is_empty = False
    
    def __init__(self, measure, left, spine, right):
        """
        Creates a Deep instance using the specified measure (an instance of
        Measure), left buffer (an instance of Digit), spine (or nested tree; an
        instance of Tree whose values are Node instances), and right buffer
        (also an instance of Digit).
        """
        self.measure = measure
        self.annotation = measure.operator(measure.operator(left.annotation, spine.annotation), right.annotation)
        self.left = left
        self.spine = spine
        self.right = right
    
    def get_first(self):
        """
        Returns this tree's first value.
        
        Time complexity: O(1).
        """
        return self.left[0]
    
    def without_first(self):
        """
        Returns a new Tree instance representing this tree with its first item
        removed.
        
        Time complexity: amortized O(1).
        """
        # If we have more than one value in the left digit, just return a tree
        # with the leftmost value in the digit removed.
        if len(self.left) > 1:
            return Deep(self.measure, self.left[1:], self.spine, self.right)
        # If we only have one value left but the spine isn't empty, overwrite
        # the digit with its leftmost value (thereby dropping the single item
        # contained within the digit).
        elif not self.spine.is_empty:
            return Deep(self.measure, Digit(self.measure, *self.spine.get_first()), self.spine.without_first(), self.right)
        # If the spine's empty and the right digit only has one item, return a
        # Single instance containing that item.
        elif len(self.right) == 1:
            return Single(self.measure, self.right[0])
        # If the spine's empty but the right digit contains two or more items,
        # move its first item into the leftmost digit, dropping the single item
        # that was already there.
        else:
            return Deep(self.measure, self.right[0:1], self.spine, self.right[1:])
    
    def add_first(self, new_item):
        """
        Returns a new Tree instance representing this tree with the specified
        item at the beginning.
        
        Time complexity: amortized O(1).
        """
        # If we have less than four items in our leftmost digit, just add this
        # item to it.
        if len(self.left) < 4:
            return Deep(self.measure, Digit(self.measure, new_item) + self.left, self.spine, self.right)
        # Otherwise, pop three items off of the digit and shove a Node
        # containing them onto our spine, then add this item. TODO: It'd
        # probably be possible to get rid of the second line of this else
        # statement by having the first line be enclosed in an if statement
        # and have the bit that appends to the digit be outside of the if
        # statement.
        else:
            node = Node(self.measure, self.left[1], self.left[2], self.left[3])
            return Deep(self.measure, Digit(self.measure, new_item, self.left[0]), self.spine.add_first(node), self.right)
    
    # get_last, without_last, and add_last are symmetrical to get_first,
    # without_first, and add_first.
    
    def get_last(self):
        """
        Returns this tree's last value.
        
        Time complexity: O(1).
        """
        return self.right[-1]
    
    def without_last(self):
        """
        Returns a new Tree instance representing this tree with its last item
        removed.
        
        Time complexity: amortized O(1).
        """
        if len(self.right) > 1:
            return Deep(self.measure, self.left, self.spine, self.right[:-1])
        elif not self.spine.is_empty:
            return Deep(self.measure, self.left, self.spine.without_last(), Digit(self.measure, *self.spine.get_last()))
        elif len(self.left) == 1:
            return Single(self.measure, self.left[0])
        else:
            return Deep(self.measure, self.left[0:-1], self.spine, self.left[-1:])
    
    def add_last(self, new_item):
        """
        Returns a new Tree instance representing this tree with the specified
        item at the end.
        
        Time complexity: amortized O(1).
        """
        if len(self.right) < 4:
            return Deep(self.measure, self.left, self.spine, self.right + Digit(self.measure, new_item))
        else:
            node = Node(self.measure, self.right[0], self.right[1], self.right[2])
            return Deep(self.measure, self.left, self.spine.add_last(node), Digit(self.measure, self.right[3], new_item))
    
    def prepend(self, other):
        """
        Returns a new tree representing the specified tree's items followed by
        this tree's items. This is just short for other.append(self).
        """
        return other.append(self)
    
    def append(self, other):
        """
        Concatenate the specified tree onto the end of this tree.
        
        Note that this tree and the other tree must use the same measure. If
        they don't, the resulting tree will pick one of their measures to use
        arbitrarily, which will likely cause pain and headaches if the two
        measures aren't designed to work with values produced by each other.
        
        Time complexity: amortized O(log min(m, n)), where m and n are the
        number of items stored in self and other, respectively. As a result,
        appending a tree of length 1 to another tree runs in amortized O(1)
        time.
        """
        if not isinstance(other, Deep):
            return other.prepend(self)
        # Use our left digit and the specified tree's right digit, and use
        # self._fold_up to merge the two other digits into our spine.
        return Deep(self.measure, self.left, self._fold_up(self, other), other.right)
    
    def _fold_up(self, left_tree, right_tree):
        # Build a list of the left tree's right digit's items and the right
        # tree's left digit's items. There will be at least 2 and at most 8 of
        # these items.
        middle_items = list(left_tree.right) + list(right_tree.left)
        spine = left_tree.spine
        # Then iterate until we're out of items, pushing Nodes of 2 or 3 items
        # onto the former left spine.
        while middle_items:
            # Could be optimized to not remove items from the front of a list,
            # which is a bit slow; perhaps reverse middle_items and pop from
            # the end of the list, or use a sliding index that we increment as
            # we go and don't modify the list at all
            if len(middle_items) == 2 or len(middle_items) == 4:
                spine = spine.add_last(Node(self.measure, middle_items[0], middle_items[1]))
                del middle_items[0:2]
            else:
                spine = spine.add_last(Node(self.measure, middle_items[0], middle_items[1], middle_items[2]))
                del middle_items[0:3]
        # Then append the right spine and we're done!
        return spine.append(right_tree.spine)
    
    def partition_with(self, predicate, initial_annotation):
        """
        Partitions this tree around the specified monotonic predicate function.
        predicate is a function that takes a value in the monoid under which
        this tree's measure operates (i.e. a value returned from
        self.measure.convert(...)) and returns False or True.
        initial_annotation is a value to be combined (with
        self.measure.operator) with items before passing them to the predicate.
        
        The return value will be a tuple (left, right), where left is a tree
        containing the items just before the predicate transitioned from False
        to True and right is a tree containing the items after said transition.
        If the predicate returns False or True for every value it's passed,
        then right or left, respectively, will be empty.
        
        Note that the predicate need not necessarily be monotonic, but if it
        isn't, the particular False -> True transition on which the tree will
        be split is arbitrary. A monotonic predicate will give rise to exactly
        one such transition, so the location of the split will be
        deterministic.
        
        (For those unfamiliar with the term, a monotonic function is a function
        from one set of ordered values to another that maintains the relative
        order of the items given to it. In other words, the predicate function
        is monotonic if, when called on the monoidal value corresponding to
        every item in this tree, it returns False for the first m of them and
        then switches to returning True for the remaining n items.)
        
        See MeasureItemCount's docstring for an example of how to use this
        function.
        
        Time complexity: O(log min(m, n)), where m and n are the sizes of the
        resulting trees. As a result, splitting a tree with a predicate such
        that the left or right result tree has only one item (or zero items)
        runs in O(1) time. 
        """
        # Compute our left digit's annotation with the initial annotation
        # factored in
        left_annotation = self.measure.operator(initial_annotation, self.left.annotation)
        # Do the same for the spine's annotation, tracking it relative to the
        # left digit's annotation
        spine_annotation = self.measure.operator(left_annotation, self.spine.annotation)
        # Then see if the split happens in our left digit
        if predicate(left_annotation):
            # Split is in the left digit. Partition the digit and return a tree
            # containing the first half of the digit and a tree combining the
            # last half of the digit and our spine and right digit.
            left_items, right_items = self.left.partition_digit(initial_annotation, predicate)
            return to_tree(self.measure, left_items), deep_left(self.measure, right_items, self.spine, self.right)
        elif predicate(spine_annotation):
            # Split is somewhere in the spine. Partition the spine itself,
            # which will result in the node in which the split occurs being the
            # first node in the right half of the partition.
            left_spine, right_spine = self.spine.partition_with(predicate, left_annotation)
            # Rightmost node in right_spine is the one where the predicate
            # became true (and note that right_spine will never be empty; if it
            # were, the predicate wouldn't have become true on our spine at
            # all), so we need to extract it...
            split_node = right_spine.get_first()
            right_spine = right_spine.without_first()
            # ...and then split it up. We use an intermediate Digit just for
            # convenience so that I don't have to write the split logic into
            # the Node class as well.
            before_digit, after_digit = Digit(self.measure, *split_node).partition_digit(self.measure.operator(left_annotation, left_spine.annotation), predicate)
            # Then we return two new trees constructed from the two halves of the split.
            return deep_right(self.measure, self.left, left_spine, before_digit), deep_left(self.measure, after_digit, right_spine, self.right)
        else:
            # Split is in the right digit. Do exactly what we did when the
            # split was in the left digit.
            left_items, right_items = self.right.partition_digit(spine_annotation, predicate)
            return deep_right(self.measure, self.left, self.spine, left_items), to_tree(self.measure, right_items)
    
    def __repr__(self):
        return "<Deep: left=%r, spine=%r, right=%r>" % (self.left, self.spine, self.right)


def value_iterator(tree):
    """
    A generator function that yields each value from the given tree in
    succession.
    
    Each item is yielded in amortized O(1) time, so a full iteration requires
    O(n) time.
    
    The returned iterator only holds references to values that have yet to be
    produced; values earlier on in the tree will not be held on to, and as such
    can be garbage collected if nothing else holds references to them.
    """
    while not tree.is_empty:
        yield tree.get_first()
        tree = tree.without_first()
    





















