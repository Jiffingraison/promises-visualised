# promises-visualised
An interactive educational tool for exploring concurrent program executions under Promising Semantics (Kang et al., 2017). Built for MSc dissertation at Heriot-Watt University. Allows step-by-step visualization of memory states, thread views, promises, and certification.

MSc Software Engineering Dissertation Project - Heriot-Watt University  
Student: Jiffin Mathew Graison (H00493231)  
Supervisor: Dr. Marko Doko

---

## Overview

Promises Visualised is an educational desktop application that allows users to interactively explore how concurrent programs behave under the [Promising Semantics](https://sf.snu.ac.kr/promise-concurrency/) weak memory model (Kang et al., 2017).

Unlike model checkers that exhaustively enumerate executions, this tool lets users **manually guide** execution step by step - choosing which thread to run, which memory message to read, and whether to make speculative promises. This hands-on approach helps learners develop intuition for weak memory behaviours that are otherwise difficult to understand.

### Key Features

- Step-by-step execution - select threads, pick messages, observe state changes
- Promises and certification - make speculative future writes and see if they pass certification
- Memory visualisation - graphical message chains showing each location's write history
- Execution timeline - colour-coded thread lanes showing the sequence of actions
- Promise lifecycle - visual tracker showing CREATED -> CERTIFIED -> FULFILLED (or FAILED)
- Release/Acquire semantics - view front propagation via `.rel` and `.acq` access modes
- OOTA prevention - certification correctly rejects circular dependencies
- Backtracking - undo any action with Ctrl+Z
- Built-in code editor - write programs directly in the GUI
- Dockable panels - rearrange, detach, and float any panel (multi-monitor support)

---
### Prerequisites

- Python 3.10 or later

## Usage

### GUI (recommended)

python gui.py


Or load a program file directly:

python gui.py examples/store_buffering.txt

How to use the GUI:

1. Click **Load Program** or type a program in the **Code Editor** and click **Run Editor**
2. Select a thread from the **Thread** dropdown
3. Click **Execute** to run the next instruction, or **Promise** to make a speculative write
4. If a read instruction needs a message choice, pick from the dropdown and click **Confirm Read**
5. Observe changes in the **Memory**, **Timeline**, **Promise Lifecycle**, and **Threads** panels
6. Use **Undo** (or Ctrl+Z) to backtrack and explore different execution paths
7. Drag any panel's title bar to detach it as a floating window


## Input Language

Programs consist of thread blocks with simple instructions:

# Store Buffering
Thread 1:
    x = 1
    r1 = y

Thread 2:
    y = 1
    r2 = x


### Syntax Reference

| Operation | Syntax | Example 

| Write (relaxed) | `location = value` | `x = 1` 
| Write (release) | `location.rel = value` | `y.rel = 1` 
| Write from register | `location = register` | `x = r1` 
| Read (relaxed) | `register = location` | `r1 = x` |
| Read (acquire) | `register = location.acq` | `r1 = y.acq` 
| Conditional | `if (reg == val): ... end` | `if (r1 == 1): x = 1 end` 
| Loop | `while (reg != val): ... end` | `while (r1 != 1): r1 = x end` 
| Comment | `# text` | `# Store Buffering` 

- Global locations (x, y, flag, data, ...) - shared memory, visible to all threads
- Local registers (r1, r2, r10, ...) - private to each thread, pattern: `r` followed by digits
- Access modes : `.rel` (release, writes only), `.acq` (acquire, reads only), default is relaxed

---

## Example Programs

### Store Buffering (`examples/store_buffering.txt`)

```
Thread 1:
    x = 1
    r1 = y

Thread 2:
    y = 1
    r2 = x
```

Demonstrates weak memory outcomes. Try making promises to see how speculative writes affect execution.

### Message Passing with Release/Acquire (`examples/message_passing.txt`)

```
Thread 1:
    x = 1
    y.rel = 1

Thread 2:
    r1 = y.acq
    r2 = x
```

Demonstrates how release/acquire ordering guarantees that if the flag is seen, the data is also seen.

### Out-of-Thin-Air (`examples/oota.txt`)

```
Thread 1:
    r1 = y
    if (r1 == 1):
        x = 1
    end

Thread 2:
    r2 = x
    if (r2 == 1):
        y = 1
    end
```

Try promising x=1 for Thread 1 -> certification will reject it, preventing the OOTA outcome.

---

## Project Structure

```
promises-visualised/
├── run.py                    # Command-line interactive runner
├── gui.py                    # PyQt5 GUI with dockable panels
├── pyrightconfig.json        # VS Code import resolution helper
├── src/
│   ├── __init__.py           # Package marker
│   ├── instructions.py       # Instruction classes (Read, Write, If, Loop)
│   ├── state.py              # Data structures (Message, Memory, Thread, Machine, Promise)
│   ├── parser.py             # Text parser (three-layer architecture)
│   └── execution_engine.py   # Execution logic, promises, certification
├── examples/
│   ├── store_buffering.txt   # Store Buffering litmus test
│   ├── message_passing.txt   # Message Passing with REL/ACQ
│   └── oota.txt              # Out-of-Thin-Air example
└── tests/
    ├── test_parser.py        # Parser unit tests
    └── test_engine.py        # Engine integration tests
```

### Architecture


Input Text -> Parser -> Thread Objects -> Machine (Threads + Memory)->Execution Engine -> User (choices) -> GUI (display) 


The system follows a modular design with clear separation of concerns:

- Language Module (`parser.py`, `instructions.py`) - parses input into instruction objects
- State Layer (`state.py`) - holds all execution state (memory, threads, promises)
- Execution Engine (`execution_engine.py`) - implements operational semantics
- Frontend (`gui.py` or `run.py`) - displays state and collects user input

The engine has no knowledge of the GUI. The command-line runner and GUI are interchangeable frontends.

---

## Theoretical Background

This tool implements the operational semantics from:

> Kang, J., Hur, C., Lahav, O., Vafeiadis, V. and Dreyer, D. (2017) 'A Promising Semantics for Relaxed-Memory Concurrency', *Proceedings of the 44th ACM SIGPLAN Symposium on Principles of Programming Languages (POPL)*.

Key concepts modelled:

- Memory as message lists - each location stores a list of timestamped messages, not a single value
- View fronts - each thread tracks the minimum timestamp it can read from per location
- Release/Acquire - release writes bundle the writer's view; acquire reads absorb it
- Promises - threads can speculatively commit future writes, making them visible early
- Certification - ensures a thread can reach its promised write by executing alone, preventing Out-of-Thin-Air values

---

## License

This project was developed as part of an MSc dissertation at Heriot-Watt University.

---

## References

- Kang, J. et al. (2017) 'A Promising Semantics for Relaxed-Memory Concurrency', POPL
- Lamport, L. (1979) 'How to Make a Multiprocessor Computer That Correctly Executes Multiprocess Programs'
- Doko, M. (2021) PhD Thesis, MPI-SWS
- Maranget, L., Sarkar, S. and Sewell, P. (2012) 'A Tutorial Introduction to the ARM and POWER Relaxed Memory Models'