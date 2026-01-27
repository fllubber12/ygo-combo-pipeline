Combo Enumeration
=================

The core exhaustive combo enumeration engine.

This module contains the main ``EnumerationEngine`` class that explores
all possible action sequences from a starting game state.

Key Features
------------

* **Forward replay** - No save/restore, just replay from initial state
* **Branch at IDLE** - Explores all actions plus PASS at each idle point
* **SELECT_CARD branching** - Explores all valid card selections
* **Auto-decline chains** - Opponent has no responses (solitaire mode)
* **PASS creates terminals** - Each PASS action records a terminal state

Module Contents
---------------

.. automodule:: src.ygo_combo.combo_enumeration
   :members:
   :undoc-members:
   :show-inheritance:
   :exclude-members: _signal_handler, _shutdown_requested
