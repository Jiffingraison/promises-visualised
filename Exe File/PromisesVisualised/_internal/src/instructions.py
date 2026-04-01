from enum import Enum
from typing import List, Optional
from dataclasses import dataclass


#Access Mode

class AccessMode(Enum):
    RLX = "rlx"   # Relaxed
    ACQ = "acq"    # Acquire (reads only)
    REL = "rel"    # Release (writes only)


#Condition for IF and LOOP

class Condition:
    #Supports: register == value, register != value
    
    def __init__(self, register: str, operator: str, value: int):
        if operator not in ("==", "!="):
            raise ValueError(f"Unsupported operator: {operator}. Use '==' or '!='.")
        self.register = register
        self.operator = operator
        self.value = value

    def evaluate(self, env: dict) -> bool:
        #Evaluate condition against a local environment (register -> value mapping)
        if self.register not in env:
            raise RuntimeError(f"Register '{self.register}' not found in local environment.")
        actual = env[self.register]
        if self.operator == "==":
            return actual == self.value
        else:  # !=
            return actual != self.value

    def __repr__(self):
        return f"({self.register} {self.operator} {self.value})"


#Base Instruction

class Instruction:
    """Base class for all instructions"""
    pass


#Read Instruction

@dataclass
class Read(Instruction):
    # Read from a global location into a local register.
    target: str       # Local register to store the value 
    location: str     # Global memory location to read from 
    mode: AccessMode  # RLX or ACQ

    def __repr__(self):
        mode_str = f".{self.mode.value}" if self.mode != AccessMode.RLX else ""
        return f"{self.target} = {self.location}{mode_str}"


#Write Instruction

@dataclass
class Write(Instruction):
    """
    Write a value to a global location.
    The value can be an integer literal or the contents of a local register.
    """
    location: str              # Global memory location
    value_literal: Optional[int]    # If writing a constant 
    value_register: Optional[str]   # If writing from a register ("r1")
    mode: AccessMode                # RLX or REL

    def __repr__(self):
        mode_str = f".{self.mode.value}" if self.mode != AccessMode.RLX else ""
        val = self.value_literal if self.value_literal is not None else self.value_register
        return f"{self.location}{mode_str} = {val}"

    def resolve_value(self, env: dict) -> int:
        #Get the actual integer value to write, resolving register if needed
        if self.value_literal is not None:
            return self.value_literal
        if self.value_register not in env:
            raise RuntimeError(f"Register '{self.value_register}' not found in local environment.")
        return env[self.value_register]


#Control Flow Instructions

@dataclass
class If(Instruction):
    """
    Conditional branch
    - Check condition
    - If true- prepend true_branch instructions to the program
    - If false- prepend false_branch instructions to the program
    """
    condition: Condition
    true_branch: List[Instruction]
    false_branch: List[Instruction]  # Can be empty (no else)

    def __repr__(self):
        return f"if {self.condition}"


@dataclass
class Loop(Instruction):
    """
    Loop construct.
    - Check condition
    - If true- unroll one body, prepend body + this loop back to program
    - If false- discard this loop, continue with remaining program
    """
    condition: Condition
    body: List[Instruction]

    def __repr__(self):
        return f"while {self.condition}"



