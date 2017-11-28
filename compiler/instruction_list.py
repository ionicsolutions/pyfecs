import logging

from ..objects.exceptions import *
from .instructions import SetInstruction, InstructionBits


class InstructionList:
    def __init__(self):
        self.logger = logging.getLogger("PyFECS.compile.InstructionList")
        self.list = []
        self.stack = []

        self._big_list = []
        self._original_block_times = {}
        self._block_ranges = {}
        self.control_register_high_time = 1

    def add(self, *instructions):
        for instruction in instructions:
            time = instruction.time
            type_ = instruction.command
            self.list.append((time, type_, instruction))

    @property
    def sorted(self):
        return sorted(self.list)

    @property
    def instructions(self):
        return [entry[2] for entry in self.list]

    @property
    def length(self):
        return len(self.list)

    @property
    def human(self):
        msg = "block  time   typ destination of\n"
        for entry in self.list:
            msg += "{:<7}".format(str(entry[2].part_of))
            msg += format(entry[0], "#7")
            msg += " " + str(entry[1]) + "  "
            try:
                for origin in entry[2].destination_of:
                    msg += "{:<7}".format(str(origin.part_of)) + ", "
                msg = msg[:-2]
            except AttributeError:
                msg += 7*" "
            msg += "\n"
        return msg

    def sort(self):
        self.stack.append(self.list)
        self.list = sorted(self.list)

    def get_time(self, time):
        instructions = []
        for instruction_time, instruction_type, instruction in self.list:
            if instruction_time == time:
                instructions.append(instruction)
        return instructions

    @staticmethod
    def filter(list_of_instructions, instruction_class):
        filtered_list = []
        other_list = []
        for instruction in list_of_instructions:
            if isinstance(instruction, instruction_class):
                filtered_list.append(instruction)
            else:
                other_list.append(instruction)
        return filtered_list, other_list

    def compress(self, control_mask):
        self.sort()
        compressed_list = []
        for time in set([entry[0] for entry in self.list]):
            all_instructions = self.get_time(time)
            set_instructions, other_instructions = \
                self.filter(all_instructions, SetInstruction)
            if set_instructions:
                new_set_instruction = SetInstruction.combine(
                    control_mask, *set_instructions)
                compressed_list.append(new_set_instruction)
            compressed_list += other_instructions
        self.stack.append(self.list)
        self.list = []
        for instruction in compressed_list:
            self.add(instruction)
        # We need to sort the list again to prevent inheritance bugs.
        self.sort()

    def make_times_unique(self, control_register_high_time):
        self.control_register_high_time = control_register_high_time
        self.sort()
        self._big_list = range(self.list[-1][0] + 1)

        self.logger.info("Placing instruction blocks.")

        other_instructions = []
        instructions_by_block = {}
        for time, type_, instruction in self.list:
            if instruction.part_of is not None:
                try:
                    instructions_by_block[instruction.part_of].append(
                        (time, type_, instruction))
                except KeyError:
                    instructions_by_block[instruction.part_of] = [
                        (time, type_, instruction)]
            else:
                other_instructions.append((time, type_, instruction))

        self._original_block_times = {}
        block_ranges = []
        for block, members in instructions_by_block.iteritems():
            members = sorted(members)
            block_ranges.append((members[0][0], members[-1][0], block))
            if block == "_START":
                time = members[0][0]
                assert time == 0
            elif block == "_END":
                time = members[-1][0]
            else:
                time = members[-3][0]  # last two items are control register
            self._original_block_times[block] = time

        block_ranges = sorted(block_ranges)
        block_offsets = {}
        for i, entry in enumerate(block_ranges):
            start, end, block = entry
            if i > 0:
                if start > block_ranges[i - 1][1]:
                    pass
                else:
                    if block == "_END":
                        raise CompilerErrorException(
                            "The sequence is too short to place all blocks.")
                    offset = (block_ranges[i - 1][1] - start) + 1
                    block_ranges[i] = (start + offset, end + offset, block)
                    self.logger.warning(
                        "Shifting block '%s' by %d instruction steps to "
                        "leave enough room for previous block '%s'.",
                        block, offset, block_ranges[i - 1][2])
                    block_offsets[block] = offset

        self._block_ranges = {entry[2]: (entry[0], entry[1])
                              for entry in block_ranges}

        for block, instructions in instructions_by_block.iteritems():
            for time, type_, instruction in instructions:
                if self._big_list[time] == time:
                    self._big_list[time] = (time, type_, instruction)
                else:
                    raise CompilerErrorException(
                        "Detected overlap in blocks, even though blocks "
                        "have been shifted apart. This might be due to "
                        "non-unique time %d within block '%s'."
                        % (time, instruction.block))

        for time, type_, instruction in sorted(other_instructions,
                                               reverse=True):
            self._shift(time, type_, instruction)

        unique_list = []
        for i, entry in enumerate(self._big_list):
            if i != entry:
                unique_list.append(entry)

        self.stack.append(self.list)
        self.list = unique_list

    def _shift(self, time, type_, instruction,
               to_later_times=False, out_of_block=False):
        for block, range in self._block_ranges.iteritems():
            if range[0] <= time <= range[1]:
                if out_of_block and to_later_times:
                    raise CompilerErrorException(
                        "There is not enough time between block '%s' and the "
                        "previous block to place all scheduled instructions."
                        % block)
                elif out_of_block and not to_later_times:
                    raise CompilerErrorException(
                        "There is not enough time between block '%s' and the "
                        "next block to place all scheduled instructions."
                        % block)
                else:
                    self.logger.warning(
                        "Instruction %s scheduled within block '%s', shifting.")
                    if time >= self._original_block_times[block]:
                        self._shift(range[1] + 1, type_, instruction,
                                    to_later_times=True,
                                    out_of_block=True)
                    else:
                        self._shift(range[0] - 1, type_, instruction,
                                    to_later_times=False,
                                    out_of_block=True)
                    return

        if self._big_list[time] == time:
            self._big_list[time] = (time, type_, instruction)
            instruction.time = time
            return

        if out_of_block:
            # When we are moving items out of a block, we blindly push
            # everything away to preserve instruction order
            if to_later_times:
                self._shift(time + 1,
                            self._big_list[time][1],
                            self._big_list[time][2],
                            to_later_times=True,
                            out_of_block=True)
            else:
                self._shift(time - 1,
                            self._big_list[time][1],
                            self._big_list[time][2],
                            to_later_times=False,
                            out_of_block=True)
            self._big_list[time] = (time, type_, instruction)
            return

        # When there are multiple instructions at the same timestamp,
        # we always order them SET, JUMP, END. Note that two separate
        # SET instructions with different timestamps are never combined,
        # but shifted in their original order.
        # Note that at this point, only jumps from standalone GoTos remain,
        # as all other jump instructions are part of a block.
        shift = {InstructionBits.set: 0,
                 InstructionBits.jump: 1,
                 InstructionBits.end: 2}
        if to_later_times:
            new_time = time + 1
            if shift[self._big_list[time][1]] < shift[type_]:
                # the instruction already present is weaker
                # than our instruction, so we have to look further
                self._shift(new_time, type_, instruction,
                            to_later_times=True)
            else:
                # the instruction already present is stronger
                # or of equal strength, so it has to be moved
                self._shift(new_time,
                            type_=self._big_list[time][1],
                            instruction=self._big_list[time][2],
                            to_later_times=True)
                self.logger.warning(
                    "Shifting instruction '%s' to later time %d.",
                    instruction, time)
                self._big_list[time] = (time, type_, instruction)
        else:
            new_time = time - 1
            if shift[self._big_list[time][1]] > shift[type_]:
                # the instruction already present is stronger
                # than our instruction, so we have to look further
                self._shift(new_time, type_, instruction,
                            to_later_times=False)
            else:
                # the instruction already present is weaker
                # or of equal strength, so it has to be moved
                self._shift(new_time,
                            type_=self._big_list[time][1],
                            instruction=self._big_list[time][2],
                            to_later_times=False)
                self.logger.warning(
                    "Shifting instruction '%s' to earlier time %d.",
                    instruction, time)
                self._big_list[time] = (time, type_, instruction)

    def add_polarity_mask(self, polarity_mask):
        for instruction in self.instructions:
            if isinstance(instruction, SetInstruction):
                instruction.polarity_mask = polarity_mask

    def assign_addresses(self):
        self.sort()
        current_time = -1
        for i, entry in enumerate(self.list):
            time, type_, instruction = entry
            if time == current_time:
                raise CompilerErrorException(
                    "Trying to assign addresses to instructions in list which "
                    "contains more than one instruction per time step.")
            elif time < current_time:
                raise CompilerErrorException(
                    "Trying to assign addresses to instructions in list which "
                    "is not sorted properly.")
            else:
                current_time = time

            instruction.address = i
