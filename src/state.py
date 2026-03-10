import copy
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from src.instructions import Instruction



#Message

@dataclass
class Message:
    """
    A single write record in memory.
    MESSAGE = { VALUE | TIMESTAMP | METADATA (VIEW_FROM) }
    """
    value: int
    timestamp: int
    view_from: Dict[str, int] = field(default_factory=dict)

    def __repr__(self):
        return f"MSG(val={self.value}, ts={self.timestamp})"

#Promise

@dataclass
class Promise:
    """
    A record of a speculative future write
    Certification ensures the thread can actually reach the write by running alone.
    """
    thread_id: int      # which thread made this promise
    location: str       # memory location (e.g., "x")
    value: int          # promised value (e.g., 1)
    timestamp: int      # where in the message list this was placed
    fulfilled: bool = False  # has the thread executed the matching write yet?

    def __repr__(self):
        status = "fulfilled" if self.fulfilled else "pending"
        return f"Promise(T{self.thread_id}: {self.location}={self.value}, ts={self.timestamp}, {status})"


#Memory

class Memory:

    #Shared memory: maps each global location to an ordered list of Messages.

    def __init__(self):
        self._store: Dict[str, List[Message]] = {}

    def ensure_location(self, location: str):
        #Initialize a location with default Message(0, 0) if not yet present.
        if location not in self._store:
            self._store[location] = [Message(value=0, timestamp=0, view_from={})]

    def get_messages(self, location: str) -> List[Message]:
        #Get all messages for a location.
        self.ensure_location(location)
        return self._store[location]

    def add_message(self, location: str, message: Message):
        """
        Add a message to a location's message list.
        Messages are kept in timestamp order.
        """
        self.ensure_location(location)
        msgs = self._store[location]
        # Insert in timestamp order
        inserted = False
        for i, existing in enumerate(msgs):
            if message.timestamp < existing.timestamp:
                msgs.insert(i, message)
                inserted = True
                break
        if not inserted:
            msgs.append(message)

    def next_timestamp(self, location: str) -> int:
        #Get the next available timestamp for a location
        self.ensure_location(location)
        msgs = self._store[location]
        if not msgs:
            return 1
        return msgs[-1].timestamp + 1

    def get_readable_messages(self, location: str, min_timestamp: int) -> List[Message]:
        """
        Get messages that a thread can read, based on its view front for this location.
        A thread can read any message with timestamp >= min_timestamp.
        """
        self.ensure_location(location)
        return [m for m in self._store[location] if m.timestamp >= min_timestamp]

    @property
    def locations(self) -> List[str]:
        #All locations currently in memory.
        return list(self._store.keys())

    def __repr__(self):
        lines = ["Memory:"]
        for loc, msgs in self._store.items():
            msg_strs = " -> ".join(str(m) for m in msgs)
            lines.append(f"  {loc} ↦ [{msg_strs}]")
        return "\n".join(lines) if self._store else "Memory: (empty)"


#Thread 

class Thread:
    """
    A thread object in the machine.
    THREAD:
      PROGRAM: "what's left to execute" (list of Instructions)
      VIEW FRONTS: x -> time, y -> time, ...
    Also holds local registers (r1, r2, etc.) for storing read values.
    """

    def __init__(self, thread_id: int, program: List[Instruction]):
        self.thread_id = thread_id
        self.program = list(program)  # Copy — "what's left to execute"
        self.view_fronts: Dict[str, int] = {}  # location -> timestamp
        self.registers: Dict[str, int] = {}     # local registers (r1, r2, etc.)

    @property
    def is_finished(self) -> bool:
        #Thread has no more instructions to execute.
        return len(self.program) == 0

    @property
    def next_instruction(self) -> Optional[Instruction]:
        #Peek at the next instruction without removing it.
        if self.program:
            return self.program[0]
        return None

    def pop_instruction(self) -> Instruction:
        #Remove and return the next instruction.
        if not self.program:
            raise RuntimeError(f"Thread {self.thread_id} has no instructions left.")
        return self.program.pop(0)

    def prepend_instructions(self, instructions: List[Instruction]):
        """
        Insert instructions at the beginning of the program.
        Used by IF and LOOP to "put the branch at the beginning of the sequence."
        """
        self.program = instructions + self.program

    def get_view_front(self, location: str) -> int:
        """Get the minimum timestamp this thread can read from for a location."""
        return self.view_fronts.get(location, 0)

    def update_view_front(self, location: str, timestamp: int):
        """Update the thread's view of a location"""
        current = self.view_fronts.get(location, 0)
        if timestamp > current:
            self.view_fronts[location] = timestamp

    def __repr__(self):
        instr_preview = self.program[0] if self.program else "(done)"
        return (f"Thread {self.thread_id}: "
                f"next=[{instr_preview}], "
                f"regs={self.registers}, "
                f"views={self.view_fronts}")


#Machine

class Machine:
    """
    The top-level machine containing threads and shared memory.
    MACHINE = { THREAD OBJECTS + MEMORY }
    """

    def __init__(self, threads: List[Thread]):
        self.threads = threads
        self.memory = Memory()
        self.promises: List[Promise] = []  # Outstanding promises
        self._history: List = []  # For potential backtracking

    @property
    def is_finished(self) -> bool:
        #All threads have completed execution.
        return all(t.is_finished for t in self.threads)

    def get_active_threads(self) -> List[Thread]:
        #Threads that still have instructions to execute.
        return [t for t in self.threads if not t.is_finished]

    def get_thread(self, thread_id: int) -> Thread:
        #Get a thread by its ID.
        for t in self.threads:
            if t.thread_id == thread_id:
                return t
        raise ValueError(f"No thread with ID {thread_id}")
    
    def get_promises_for_thread(self, thread_id: int) -> List[Promise]:
        """Get all unfulfilled promises made by a specific thread."""
        return [p for p in self.promises if p.thread_id == thread_id and not p.fulfilled]

    def find_matching_promise(self, thread_id: int, location: str, value: int):
        """Check if a thread has an unfulfilled promise matching this write."""
        for p in self.promises:
            if (p.thread_id == thread_id and p.location == location
                    and p.value == value and not p.fulfilled):
                return p
        return None

    def initialize_memory_for_threads(self):
        """
        Scan all thread programs and ensure all global locations are
        initialized in memory.
        """
        for thread in self.threads:
            for instr in thread.program:
                self._collect_locations(instr)

    def _collect_locations(self, instr):
        #Recursively collect global locations from instructions
        from src.instructions import Read, Write, If, Loop
        if isinstance(instr, Read):
            self.memory.ensure_location(instr.location)
        elif isinstance(instr, Write):
            self.memory.ensure_location(instr.location)
        elif isinstance(instr, If):
            for sub in instr.true_branch + instr.false_branch:
                self._collect_locations(sub)
        elif isinstance(instr, Loop):
            for sub in instr.body:
                self._collect_locations(sub)

    def snapshot(self) -> dict:
        #ake a snapshot of current state for backtracking
        return copy.deepcopy({
            'threads': [(t.thread_id, list(t.program), dict(t.view_fronts), dict(t.registers))
                        for t in self.threads],
            'memory': self.memory
        })

    def __repr__(self):
        lines = ["--Machine State-- "]
        for t in self.threads:
            lines.append(f"  {t}")
        lines.append(f"  {self.memory}")
        return "\n".join(lines)