YGO-Combo-Pipeline API Reference
=================================

Welcome to the YGO-Combo-Pipeline API documentation. This package provides
Python bindings to the ygopro-core OCG library for exhaustive Yu-Gi-Oh!
combo enumeration.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   modules/types
   modules/engine
   modules/search
   modules/cards
   modules/encoding
   modules/enumeration
   modules/combo_enumeration

Overview
--------

The package is organized into several submodules:

* **types** - Shared type definitions (Action, TerminalState)
* **engine** - Core OCG bindings, interface, and state representation
* **search** - Search algorithms (IDDFS, parallel, transposition tables)
* **cards** - Card validation and role classification
* **encoding** - ML-compatible state encoding
* **enumeration** - Message parsing and response building

Quick Start
-----------

Basic imports::

    from ygo_combo import Action, TerminalState
    from ygo_combo.engine import ffi, load_library
    from ygo_combo.search import IterativeDeepeningSearch, SearchConfig
    from ygo_combo.cards import CardValidator

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
