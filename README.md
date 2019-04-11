# JungleWalker
## v1.0 Release
[CellCollective](https://cellcollective.org) Model Loader and Simulator

[CellCollective](https://cellcollective.org) is an online tool which can be used to model cellular biochemical processes as boolean networks. Jungle Walker is a tool which can load these models, and enables you to use tools like simulation and analysis to walk through the often massive jungle of nodes in these models. It currently includes several useful features, detailed below.

* Integration with the CellCollective website:
  + Models are fetched directly from the CellCollective API.
  + Users may log into CellCollective and work with private/personal models.
  + Models are cached in files after being fetched through the API, and cached models will be used unless they are outdated.
* Several built-in views which display different types of information about internal and external components of models.
* A comprehensive simulation environment:
  + A mutation dialog to configure a mutation set in which nodes may be forced to be always active or always inactive
  + A report-style list which can load various custom sets of nodes and monitor their activity levels
  + Pause and Play abilities to stop and continue the simulation
  + A logic editor which can change the logical rule for any internal component in real time
* Information tabs are hidden by default, but can be opened or closed through the "Windows" menu
* A carefully refactored analysis system:
  + Set ranges for external component values
  + Run large batches of simulation. JungleWalker uses Python's "multiprocessing" module to increase the speed of these
    batch simulations by a factor of four or more.
  + Select the timeframes from which to collect data in these simulations.
* A robust post-analysis environment:
  + After the batch of simulations from analysis is complete, the collected data is stored and a new "Post-Analysis" Tab will
    display and gain focus immediately.
  + Analysis data may be exported to a CSV file.
  + Exported analysis data can be imported into the "Post-Analysis" view to be compared against newly collected data using
    various methods.
  + Built-in methods include "Averages" and "Confidence Interval Analysis"
    + The "Averages" method is mostly a method for testing, it goes through each result of the two data sets and takes the
      average of the two results for each given node. For example if data sets A and B contain 3 results each for the node
      "Akt", [50.0, 70.0, 30.0] and [60.0, 80.0, 40.0] respectively, then the result of the Averages method will be [55.0,
      75.0, 35.0].
    + The "Confidence Interval Analysis" method calculates confidence intervals for the fold-change values between two different
      experimental groups of the nodes in the model.
  + Custom-written methods may be imported into the "Post-Analysis" view for flexible usage. This means that scripts may be
    written in Python and imported into JungleWalker to process the analysis data. Documentation on this shall be provided
    soon.
  + Imported CSV files may specify nodes by their CellCollective species ID (making the data file specific to the given model)
    or by their name (making the data flexible and usable by several models containing similar sets of nodes).
    - Note: the Export feature does not yet allow exporting CSV files which specify nodes by their CellCollective species ID.
      This will be implemented at a later date.
* A precise, navigable component map:
  + Allows zooming and shows node name labels when sufficiently zoomed in
  + Allows navigation by dragging the mouse in the map

As of version Alpha 2.2, the "Debug" menu has been removed as the developer no longer needed it.
