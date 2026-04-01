import re
from typing import List, Tuple, Optional
from src.instructions import (
    Instruction, Read, Write, If, Loop,
    AccessMode, Condition
)
from src.state import Thread


#Layer 1: Helper Functions

def is_register(name: str) -> bool:
    #Check if a name refers to a local register (r1, r2)
    return bool(re.match(r'^r\d+$', name))


def is_integer(s: str) -> bool:
    #Check if a string is an integer literal
    try:
        int(s)
        return True
    except ValueError:
        return False


def parse_condition(cond_str: str) -> Condition:
    """
    Parse a condition string like 'r1 == 1' or 'r2 != 0'.
    """
    cond_str = cond_str.strip()
    for op in ('==', '!='):
        if op in cond_str:
            parts = cond_str.split(op)
            if len(parts) != 2:
                raise SyntaxError(f"Invalid condition: '{cond_str}'")
            register = parts[0].strip()
            value = parts[1].strip()
            if not is_register(register):
                raise SyntaxError(
                    f"Condition left-hand side must be a register (e.g., r1), got '{register}'")
            if not is_integer(value):
                raise SyntaxError(
                    f"Condition right-hand side must be an integer, got '{value}'")
            return Condition(register, op, int(value))
    raise SyntaxError(f"No valid operator (== or !=) found in condition: '{cond_str}'")


def parse_location_with_mode(token: str) -> Tuple[str, Optional[AccessMode]]:
    """Parse a location that may have an access mode suffix.
    'x'       → ('x', None)
    'x.rel'   → ('x', REL)
    'x.acq'   → ('x', ACQ)
    """
    if '.rel' in token:
        return token.replace('.rel', ''), AccessMode.REL
    elif '.acq' in token:
        return token.replace('.acq', ''), AccessMode.ACQ
    return token, None


#Layer 2: Parse a Single Instruction Line 

def parse_instruction_line(line: str) -> Instruction:

    #Parse a single instruction line into an Instruction object.

    line = line.strip()

    # Must be an assignment: LHS = RHS
    if '=' not in line or line.startswith('if') or line.startswith('while'):
        raise SyntaxError(f"Expected assignment instruction, got: '{line}'")

    # Find the assignment '=' (not '==' or '!=')
    # Scan character by character to avoid matching == or !=
    eq_pos = None
    i = 0
    while i < len(line):
        if line[i] == '=' and (i == 0 or line[i-1] not in ('!', '=')) and \
           (i + 1 >= len(line) or line[i+1] != '='):
            eq_pos = i
            break
        i += 1

    if eq_pos is None:
        raise SyntaxError(f"No assignment found in: '{line}'")

    lhs = line[:eq_pos].strip()
    rhs = line[eq_pos+1:].strip()

    if not lhs or not rhs:
        raise SyntaxError(f"Empty left or right side in: '{line}'")

    # Parse both sides for location names and access modes
    lhs_name, lhs_mode = parse_location_with_mode(lhs)
    rhs_name, rhs_mode = parse_location_with_mode(rhs)

    if is_register(lhs_name):
        # READ: r1 = x  or  r1 = x.acq
        # Register on left → reading from memory into register
        location = rhs_name
        mode = rhs_mode if rhs_mode else AccessMode.RLX

        if mode == AccessMode.REL:
            raise SyntaxError(f"Cannot use .rel on a read: '{line}'. Use .acq for acquire reads.")

        if is_register(rhs_name) or is_integer(rhs_name):
            raise SyntaxError(
                f"Read must be from a global location, not a register or literal: '{line}'")

        return Read(target=lhs_name, location=location, mode=mode)
    else:
        # WRITE: x = 1  or  x = r1  or  x.rel = 1
        # Non-register on left → writing to memory
        location = lhs_name
        mode = lhs_mode if lhs_mode else AccessMode.RLX

        if mode == AccessMode.ACQ:
            raise SyntaxError(f"Cannot use .acq on a write: '{line}'. Use .rel for release writes.")

        if is_integer(rhs):
            return Write(location=location, value_literal=int(rhs),
                         value_register=None, mode=mode)
        elif is_register(rhs):
            return Write(location=location, value_literal=None,
                         value_register=rhs, mode=mode)
        else:
            # RHS is another global — not supported (no global-to-global copy)
            raise SyntaxError(
                f"Write value must be an integer or register, got '{rhs}' in: '{line}'")


#Layer 3: Parse Blocks and Full Programs 

def parse_block(lines: List[str], start: int) -> Tuple[List[Instruction], int]:
    """
    Parse a block of instructions from 'start' until 'end', 'else:', or end of lines.
    Returns (instructions, next_line_index).
    """
    instructions = []
    i = start

    while i < len(lines):
        line = lines[i].strip()

        # Skip empty lines and comments
        if not line or line.startswith('#'):
            i += 1
            continue

        # Block terminators
        if line == 'end' or line == 'else:':
            return instructions, i

        # Thread header — stop, we've hit the next thread
        if re.match(r'^Thread\s+\d+\s*:', line, re.IGNORECASE):
            return instructions, i

        # IF statement
        if_match = re.match(r'^if\s*\((.+)\)\s*:', line)
        if if_match:
            condition = parse_condition(if_match.group(1))
            # Parse true branch (recurse)
            true_branch, next_i = parse_block(lines, i + 1)
            false_branch = []
            # Check for else
            if next_i < len(lines) and lines[next_i].strip() == 'else:':
                false_branch, next_i = parse_block(lines, next_i + 1)
            # Expect 'end'
            if next_i < len(lines) and lines[next_i].strip() == 'end':
                next_i += 1
            else:
                raise SyntaxError(
                    f"Missing 'end' for 'if' at line {i + 1}")
            instructions.append(If(condition, true_branch, false_branch))
            i = next_i
            continue

        # WHILE loop
        while_match = re.match(r'^while\s*\((.+)\)\s*:', line)
        if while_match:
            condition = parse_condition(while_match.group(1))
            # Parse loop body (recurse)
            body, next_i = parse_block(lines, i + 1)
            # Expect 'end'
            if next_i < len(lines) and lines[next_i].strip() == 'end':
                next_i += 1
            else:
                raise SyntaxError(
                    f"Missing 'end' for 'while' at line {i + 1}")
            instructions.append(Loop(condition, body))
            i = next_i
            continue

        # Regular instruction (read or write)
        instructions.append(parse_instruction_line(line))
        i += 1

    return instructions, i


def parse_program(text: str) -> List[Thread]:
    
    #Parse a complete program text into a list of Thread objects.

    lines = text.split('\n')
    threads = []
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Skip empty lines and comments
        if not line or line.startswith('#'):
            i += 1
            continue

        # Look for thread headers
        thread_match = re.match(r'^Thread\s+(\d+)\s*:', line, re.IGNORECASE)
        if thread_match:
            thread_id = int(thread_match.group(1))
            # Parse the thread's instruction block
            instructions, next_i = parse_block(lines, i + 1)
            threads.append(Thread(thread_id, instructions))
            i = next_i
            continue

        # If we're outside a thread block, it's an error
        raise SyntaxError(f"Unexpected line outside thread block at line {i + 1}: '{line}'")

    if not threads:
        raise SyntaxError("No threads found in the program.")

    return threads


def parse_file(filepath: str) -> List[Thread]:
    #Parse a program from a file
    with open(filepath, 'r') as f:
        text = f.read()
    return parse_program(text)