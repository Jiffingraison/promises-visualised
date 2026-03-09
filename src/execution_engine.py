import copy
from typing import List, Tuple, Optional
from src.instructions import (
    Instruction, Read, Write, If, Loop,
    AccessMode, Condition
)
from src.state import Thread, Memory, Message, Machine


# Choice Classes 
# When the engine needs user input before it can proceed,
# it returns one of these objects to the caller

class ReadChoice:
    """
    Returned when a thread wants to READ and the user must pick a message.
    Contains the thread, the read instruction, and the list of available messages.
    """
    def __init__(self, thread: Thread, instruction: Read,
                 available_messages: List[Message]):
        self.thread = thread
        self.instruction = instruction
        self.available_messages = available_messages


#Execution Engine

class ExecutionEngine:
    def __init__(self, machine: Machine):
        self.machine = machine
        self.step_count = 0
        self._history: List = []  # State snapshots for backtracking

    def save_state(self):
        """Save current state for backtracking."""
        self._history.append(self.machine.snapshot())

    def get_active_threads(self) -> List[Thread]:
        """Get threads that still have instructions."""
        return self.machine.get_active_threads()

    # ─── Execute: Read ───────────────────────────────────────────────────

    def execute_read(self, thread: Thread, instr: Read,
                     chosen_message: Message):
        
        #Execute a read instruction with the user's chosen message.

        # Store value in register
        thread.registers[instr.target] = chosen_message.value

        # Update view front: thread has now "seen" up to this timestamp
        thread.update_view_front(instr.location, chosen_message.timestamp)

        # Acquire semantics: absorb the writer's view
        if instr.mode == AccessMode.ACQ and chosen_message.view_from:
            for loc, ts in chosen_message.view_from.items():
                thread.update_view_front(loc, ts)

        # Remove instruction from program
        thread.pop_instruction()
        self.step_count += 1

    # ─── Execute: Write ──────────────────────────────────────────────────

    def execute_write(self, thread: Thread, instr: Write,
                      timestamp: Optional[int] = None):
        # Resolve value
        value = instr.resolve_value(thread.registers)

        # Determine timestamp
        if timestamp is None:
            timestamp = self.machine.memory.next_timestamp(instr.location)

        # Build view_from metadata for release writes
        view_from = {}
        if instr.mode == AccessMode.REL:
            view_from = dict(thread.view_fronts)
            # Include current write's location at the new timestamp
            view_from[instr.location] = timestamp

        # Create and add message
        msg = Message(value=value, timestamp=timestamp, view_from=view_from)
        self.machine.memory.add_message(instr.location, msg)

        # Update thread's own view front
        thread.update_view_front(instr.location, timestamp)

        # Remove instruction from program
        thread.pop_instruction()
        self.step_count += 1

    # Execute: IF
    def execute_if(self, thread: Thread, instr: If):
        
        # Remove the IF from the program first
        thread.pop_instruction()

        # Evaluate condition
        result = instr.condition.evaluate(thread.registers)

        # Prepend the appropriate branch
        if result:
            thread.prepend_instructions(list(instr.true_branch))
        else:
            thread.prepend_instructions(list(instr.false_branch))

        self.step_count += 1

    # Execute: LOOP 

    def execute_loop(self, thread: Thread, instr: Loop):
   
        # Remove the LOOP from the program first
        thread.pop_instruction()

        # Evaluate condition
        result = instr.condition.evaluate(thread.registers)

        if result:
            # Unroll one iteration: prepend body + the loop itself
            # (loop goes back after body so it can be re-evaluated)
            unrolled = list(instr.body) + [Loop(instr.condition, list(instr.body))]
            thread.prepend_instructions(unrolled)
        # If false: loop is discarded, program continues with whatever follows

        self.step_count += 1

    # Finding Available Messages 

    def get_available_messages_for_read(self, thread: Thread,
                                        instr: Read) -> List[Message]:
      
        min_ts = thread.get_view_front(instr.location)
        return self.machine.memory.get_readable_messages(instr.location, min_ts)

    # Main Step Method 

    def step_thread(self, thread: Thread, read_choice: Optional[Message] = None,
                    write_timestamp: Optional[int] = None):
       
        if thread.is_finished:
            return None

        instr = thread.next_instruction

        if isinstance(instr, Read):
            available = self.get_available_messages_for_read(thread, instr)
            if not available:
                raise RuntimeError(
                    f"Thread {thread.thread_id}: No readable messages for {instr.location}")

            if read_choice is None:
                # Need user to choose
                return ReadChoice(thread, instr, available)

            self.execute_read(thread, instr, read_choice)
            return None

        elif isinstance(instr, Write):
            self.execute_write(thread, instr, write_timestamp)
            return None

        elif isinstance(instr, If):
            self.execute_if(thread, instr)
            return None

        elif isinstance(instr, Loop):
            self.execute_loop(thread, instr)
            return None

        else:
            raise RuntimeError(f"Unknown instruction type: {type(instr)}")