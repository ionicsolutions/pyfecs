import copy

from .exceptions import FECSException, InvalidSequenceException
from jumps import Terminator, Jump, Pass
from timePoints import TimePoint, ReferenceType


class Loop:
    def __init__(self, end):
        self.end = end


class Tree:
    MAX_DEPTH = 100

    def __init__(self, sequence, control_values):
        self.sequence = sequence
        self.control_values = control_values

        self.tree = {}

        self._objects = {}

        self._depth = 0
        self._terminator_count = 0
        self._branch_terminator = {}

        all_jumps = sequence.jumps.values()
        all_times = [(jump.get_time(control_values), jump) for jump in all_jumps]
        self.sorted_jumps = sorted(all_times)

    def build(self):
        try:
            first_jump = self.sorted_jumps[0][1]
        except IndexError:
            self.tree = { Terminator() : Terminator()}
        else:
            self._objects[first_jump.name] = first_jump
            self.tree[first_jump.name] = self._branch(first_jump, [])

    @staticmethod
    def _resolve_object(destination):
        if destination.type == ReferenceType.start:
            return destination.object.start
        elif destination.type == ReferenceType.end:
            return destination.object.end
        else:
            return destination.object

    def _branch(self, point, branch_history):
        self._depth += 1
        if self._depth > self.MAX_DEPTH:
            return None
        branch = {}
        if isinstance(point, Jump):
            if point.name in branch_history:
                self._depth = 0
                return Loop(point.name)
            else:
                try:
                    new_branch_history = copy.deepcopy(branch_history)
                except TypeError as e:
                    # TODO: Figure out the exact reason for this problem
                    # So far, this has only happened for sequences which contain
                    # an infinite loop within the sequence, i.e. a circular
                    # chain of Jump instances
                    raise InvalidSequenceException(
                        msg="copy.deepcopy of branch history failed with "
                            "TypeError ('%s'). This points to an infinite "
                            "sub loop, i.e. a loop which the sequence can jump "
                            "into but not leave. History: %s "
                            "We are at point %s (%s)"
                            % (e, branch_history, point, point.name),
                        object=self)
                else:
                    new_branch_history.append(point.name)
                    self._objects[point.name] = point
            for destination in point.compressed_conditions.values():
                object_ = self._resolve_object(destination)
                try:
                    name = object_._name
                except AttributeError:
                    name = str(object_)
                self._objects[name] = object_
                branch[name] = self._branch(object_,
                                               new_branch_history)
        elif isinstance(point, TimePoint):
            point_time = point.get_time(self.control_values)
            next_jump = self._next_jump(point_time)
            branch_history.append(str(point))
            self._objects[str(point)] = point
            branch[next_jump.name] = self._branch(next_jump, branch_history)
        elif isinstance(point, Terminator):
            self._depth = 0
            return point
        elif isinstance(point, Pass):
            # find the jump this Pass belongs to
            last_jump = None
            for past_point in reversed(branch_history):
                if isinstance(self._objects[past_point], Jump):
                    last_jump = self._objects[past_point]
                    break
            if last_jump is None:
                raise FECSException("Could not find my parent Jump!")
            else:
                point_time = last_jump.get_time(self.control_values)
                next_jump = self._next_jump(point_time)
                branch_history.append(str(point))
                self._objects[str(point)] = point
                branch[next_jump.name] = self._branch(next_jump, branch_history)
        else:
            raise FECSException("Strange type: %s" % type(point))
        return branch

    def _next_jump(self, point_time):
        next_jump = None
        for time, jump in self.sorted_jumps:
            if time <= point_time:
                continue
            else:
                next_jump = jump
                break
        if next_jump is None:
            return Terminator()
        else:
            return next_jump

    def check(self):
        self._terminator_count = 0
        self._branch_terminator = {}
        self._check(self.tree)
        if self._terminator_count == 0:
            raise InvalidSequenceException("No Terminator is reached.",
                                           object=self)

    def _check(self, branch):
        for point, subbranch in branch.iteritems():
            if isinstance(subbranch, Loop):
                continue
            elif isinstance(subbranch, Terminator):
                self._terminator_count += 1
            elif isinstance(subbranch, dict):
                self._check(subbranch)
            else:
                raise InvalidSequenceException(
                    "Sequence contains infinite loops.",
                    object=self)

    def visualize(self):
        """Print the tree to the terminal."""
        print("---")
        self._visualize(self.tree, 0, 0)
        print("---")

    def _visualize(self, branch, offset, sub_offset):
        if not isinstance(branch, dict):
            print("|    "*(offset/5)
                  + "[== " + str(branch) + "==]")
            print("|    "*(offset/5))
            return
        for point, subbranch in branch.iteritems():
            if offset == 0:
                print("|")
                print("|" + "-" * sub_offset + str(point))
            else:
                print("|    "*(offset/5)
                      + "|    "*((sub_offset / 5) - 1)
                      + "|----" + str(point))
            self._visualize(subbranch, offset + sub_offset, 5)
