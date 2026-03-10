import sys
from src.parser import parse_file
from src.state import Machine
from src.execution_engine import ExecutionEngine, ReadChoice
from src.instructions import If, Loop


#Display Functions 

def display_state(machine, step):
    """Print the current machine state in a readable format."""
    print()
    print(f"{'─' * 60}")
    print(f"  Step {step}")
    print(f"{'─' * 60}")

    # Show each thread
    for thread in machine.threads:
        status = "DONE" if thread.is_finished else f"next: {thread.next_instruction}"
        regs = ", ".join(f"{k}={v}" for k, v in thread.registers.items()) if thread.registers else "none"
        views = ", ".join(f"{k}>={v}" for k, v in thread.view_fronts.items()) if thread.view_fronts else "all>=0"

        # Check for pending promises
        pending = machine.get_promises_for_thread(thread.thread_id)

        print(f"  Thread {thread.thread_id}: [{status}]")
        print(f"    registers: {regs}")
        print(f"    view fronts: {views}")

        if pending:
            promise_strs = [f"{p.location}={p.value}" for p in pending]
            print(f"    pending promises: {', '.join(promise_strs)}")

        if not thread.is_finished:
            remaining = [str(i) for i in thread.program]
            print(f"    program: {' ; '.join(remaining)}")

    # Show memory
    print()
    print("  Memory:")
    for loc in sorted(machine.memory.locations):
        msgs = machine.memory.get_messages(loc)
        msg_strs = []
        for m in msgs:
            vf = ""
            if m.view_from:
                vf = f" vf={m.view_from}"
            msg_strs.append(f"(val={m.value}, ts={m.timestamp}{vf})")
        print(f"    {loc}: {' -> '.join(msg_strs)}")

    # Show all promises
    if machine.promises:
        print()
        print("  Promises:")
        for p in machine.promises:
            print(f"    {p}")

    print(f"{'─' * 60}")


#User Input Functions

def prompt_thread_choice(active_threads):
    """Ask user which thread to execute."""
    print()
    print("  Which thread to execute?")
    for t in active_threads:
        print(f"    [{t.thread_id}] Thread {t.thread_id} — next: {t.next_instruction}")

    while True:
        try:
            choice = input("  Enter thread number: ").strip()
            thread_id = int(choice)
            if any(t.thread_id == thread_id for t in active_threads):
                return thread_id
            print(f"  Thread {thread_id} is not active. Try again.")
        except ValueError:
            print("  Please enter a valid number.")
        except EOFError:
            print("\n  Exiting.")
            sys.exit(0)


def prompt_action_choice(thread, machine):
    """Ask user whether to execute next instruction or make a promise."""
    pending = machine.get_promises_for_thread(thread.thread_id)

    print()
    print(f"  Thread {thread.thread_id} — what to do?")
    print(f"    [e] Execute next instruction: {thread.next_instruction}")
    print(f"    [p] Make a promise (speculative future write)")

    while True:
        try:
            choice = input("  Choose (e/p): ").strip().lower()
            if choice in ('e', 'p'):
                return choice
            print("  Please enter 'e' or 'p'.")
        except EOFError:
            print("\n  Exiting.")
            sys.exit(0)


def prompt_promise_details(machine):
    """Ask user for the location and value of the promise."""
    print()
    print("  What do you want to promise?")

    # Show available locations
    locs = sorted(machine.memory.locations)
    print(f"    Known locations: {', '.join(locs)}")

    while True:
        try:
            location = input("  Location (e.g., x): ").strip()
            if not location:
                print("  Please enter a location name.")
                continue
            break
        except EOFError:
            print("\n  Exiting.")
            sys.exit(0)

    while True:
        try:
            value_str = input("  Value (e.g., 1): ").strip()
            value = int(value_str)
            break
        except ValueError:
            print("  Please enter an integer.")
        except EOFError:
            print("\n  Exiting.")
            sys.exit(0)

    return location, value


def prompt_read_choice(read_choice):
    """Ask user which message to read."""
    print()
    print(f"  Thread {read_choice.thread.thread_id} wants to READ {read_choice.instruction.location}")
    print(f"  Available messages:")
    for i, msg in enumerate(read_choice.available_messages):
        vf = ""
        if msg.view_from:
            vf = f" (view_from: {msg.view_from})"
        print(f"    [{i}] value={msg.value}, timestamp={msg.timestamp}{vf}")

    while True:
        try:
            choice = input("  Choose message index: ").strip()
            idx = int(choice)
            if 0 <= idx < len(read_choice.available_messages):
                return read_choice.available_messages[idx]
            print(f"  Invalid index. Choose 0-{len(read_choice.available_messages)-1}.")
        except ValueError:
            print("  Please enter a valid number.")
        except EOFError:
            print("\n  Exiting.")
            sys.exit(0)


#Main Execution Loop

def run_interactive(filepath):

    # Parse program
    print(f"\n  Loading: {filepath}")
    try:
        threads = parse_file(filepath)
    except (SyntaxError, FileNotFoundError) as e:
        print(f"  Error: {e}")
        sys.exit(1)

    print(f"  Parsed {len(threads)} threads successfully.")

    # Initialize machine
    machine = Machine(threads)
    machine.initialize_memory_for_threads()

    engine = ExecutionEngine(machine)

    # Display initial state
    display_state(machine, engine.step_count)

    # Main execution loop
    while not machine.is_finished:
        active = machine.get_active_threads()

        if not active:
            break

        # User picks a thread
        if len(active) == 1:
            chosen_id = active[0].thread_id
            print(f"\n  (Only Thread {chosen_id} is active, auto-selecting)")
        else:
            chosen_id = prompt_thread_choice(active)

        thread = machine.get_thread(chosen_id)

        # Ask: execute or promise?
        action = prompt_action_choice(thread, machine)

        if action == 'p':
            # Make a promise
            location, value = prompt_promise_details(machine)
            print()
            print(f"  Certifying: can Thread {thread.thread_id} reach "
                  f"{location}={value} running alone?")
            result = engine.create_promise(thread, location, value)
            if result:
                print(f"  ✓ Certification PASSED — promise accepted!")
                print(f"    Message added to memory. Thread must fulfill later.")
            else:
                print(f"  ✗ Certification FAILED — promise rejected!")
                print(f"    Thread cannot reach {location}={value} by running alone.")

        else:
            # Execute next instruction
            result = engine.step_thread(thread)

            if isinstance(result, ReadChoice):
                # User needs to choose which message to read
                msg = prompt_read_choice(result)
                engine.step_thread(thread, read_choice=msg)

            # Auto-step through IF/LOOP (no user choice needed)
            while (not thread.is_finished and
                   isinstance(thread.next_instruction, (If, Loop))):
                result = engine.step_thread(thread)
                if isinstance(result, ReadChoice):
                    msg = prompt_read_choice(result)
                    engine.step_thread(thread, read_choice=msg)
                    break

        # Display updated state
        display_state(machine, engine.step_count)

    # Check for unfulfilled promises
    unfulfilled = [p for p in machine.promises if not p.fulfilled]
    if unfulfilled:
        print()
        print("  ⚠ WARNING: Unfulfilled promises remain!")
        for p in unfulfilled:
            print(f"    {p}")
        print("  This execution is INVALID — all promises must be fulfilled.")

    # Show final results
    print()
    
    print("          EXECUTION COMPLETE               ")
  
    print()
    print("  Final register values:")
    for thread in machine.threads:
        for reg, val in sorted(thread.registers.items()):
            print(f"    Thread {thread.thread_id}: {reg} = {val}")
    print()


#Entry Point 

if __name__ == '__main__':
    if len(sys.argv) < 2:
     
        sys.exit(1)

    run_interactive(sys.argv[1])