# JungleWalker
## v2.2 Alpha
[CellCollective](https://cellcollective.org) Model Loader and Simulator

[CellCollective](https://cellcollective.org) is an online tool which can be used to model cellular biochemical processes as boolean networks. Jungle Walker is a tool which can load these models, and enables you to use tools like simulation and analysis to walk through the often massive jungle of nodes in these models. It currently includes several useful features, detailed below.

* Integration with the CellCollective website:
  + Models are fetched directly from the CellCollective API.
  + Users may log into CellCollective and work with private/personal models.
  + Models are cached in files after being fetched through the API.
* Loads internal and external components into lists.
* Several built-in views which display different types of information about internal and external components of models.
* A comprehensive simulation environment:
  + A mutation dialog to configure a mutation set in which nodes may be forced to be always on or always off
  + A report-style list which can load various lists of nodes and monitor their activity levels
  + Pause and Play abilities to stop and continue the simulation
  + A logic editor which can change the logic rule for any internal component in real time
* Information tabs are hidden by default, but can be opened or closed through the "Windows" menu
* A carefully refactored analysis system:
  + Set ranges for external component values
  + Run large batches of simulation. JungleWalker uses Python's "multiprocessing" module to increase the speed of these
    batch simulations by a factor of four or more.
  + Select the timeframes from which to collect data in these simulations.
* A precise, navigable component map:
  + Allows zooming and shows node name labels when sufficiently zoomed in
  + Allows navigation by dragging the mouse in the map

As of version 2.2, the "Debug" menu has been removed as the developer no longer needed it.

CAVEATS
  + Cached models will be used until the cached file or "cache" folder is deleted
  + Some models do not have layout data for the component map, so JungleWalker will not display component maps for these models.

In the future, I intend to implement the following features

* Perform statistical analysis after the batch simulations in the Analysis view have completed.
  + The developer intends to add the capability to import your own Python script to process the data to enable great flexibility
    for all CellCollective users.
* Create random logic configurations with the same components and run various simulations to compare how well constructed models actually represent processes within the cell.
* Modify the logic and write back the changes.
* Visually represent simulations as large networks of nodes, colored differently when activated or deactivated
* Add new nodes and configure their logics

I hope that eventually, the developers at CellCollective consider integrating this system into their platform.
