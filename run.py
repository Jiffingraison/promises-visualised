import sys
from src.parser import parse_file
from src.state import Machine
from src.execution_engine import ExecutionEngine, ReadChoice
from src.instructions import If, Loop


#Display Functions

def display_state(machine, step):
    #Print the current machine state in a readable format
    print()
    print(f"{'─' * 60}")
    print(f"  Step {step}")
    print(f"{'─' * 60}")

    # Show each thread
    for thread in machine.threads:
        status = "DONE" if thread.is_finished else f"next: {thread.next_instruction}"
        regs = ", ".join(f"{k}={v}" for k, v in thread.registers.items()) if thread.registers else "none"
        views = ", ".join(f"{k}>={v}" for k, v in thread.view_fronts.items()) if thread.view_fronts else "all>=0"

        print(f"  Thread {thread.thread_id}: [{status}]")
        print(f"    registers: {regs}")
        print(f"    view fronts: {views}")

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

    print(f"{'─' * 60}")


#User Input Functions

def prompt_thread_choice(active_threads):
    #Ask user which thread to execute.
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


def prompt_read_choice(read_choice):
    #Ask user which message to read
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

    #Parse program
    print(f"\n  Loading: {filepath}")
    try:
        threads = parse_file(filepath)
    except (SyntaxError, FileNotFoundError) as e:
        print(f"  Error: {e}")
        sys.exit(1)

    print(f"  Parsed {len(threads)} threads successfully.")

    #Initialize machine
    machine = Machine(threads)
    machine.initialize_memory_for_threads()

    engine = ExecutionEngine(machine)

    #Display initial state
    display_state(machine, engine.step_count)

    #Main execution loop
    while not machine.is_finished:
        active = machine.get_active_threads()

        if not active:
            break

        #User picks a thread
        if len(active) == 1:
            chosen_id = active[0].thread_id
            print(f"\n  (Only Thread {chosen_id} is active, auto-selecting)")
        else:
            chosen_id = prompt_thread_choice(active)

        thread = machine.get_thread(chosen_id)

        #Try to execute the next instruction
        result = engine.step_thread(thread)

        if isinstance(result, ReadChoice):
            # User needs to choose which message to read
            msg = prompt_read_choice(result)
            engine.step_thread(thread, read_choice=msg)

        while (not thread.is_finished and
               isinstance(thread.next_instruction, (If, Loop))):
            result = engine.step_thread(thread)
            if isinstance(result, ReadChoice):
                msg = prompt_read_choice(result)
                engine.step_thread(thread, read_choice=msg)
                break

        #Display updated state
        display_state(machine, engine.step_count)

    # Show final results
    print()
    print("                EXECUTION COMPLETE                  ")
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