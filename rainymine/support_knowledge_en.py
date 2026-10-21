"""Reviewed English application guides. IDs and scope match the Mongolian catalog."""
HELP = {
'exchange': ('Excel / STL / Geobank import', [
    'Use Drilling for Excel import or Read database; use Geology for STL import and export.',
    'Excel accepts .xlsx, a sheet name and column mapping. Formula/error cells and .xls/.xlsm are rejected. CSV files must be UTF-8.',
    'STL triangles carry no CRS or unit metadata. Confirm that source coordinates use project metres.',
    'SQL requires Windows ODBC, integrated authentication, canonical site views and snapshot transactions. Follow GEOBANK_SQL.md.']),
'implicit': ('RBF surfaces and pit optimization', [
    'Geology → RBF grade surface: configure cutoff, composites, resolution and bounds. This extrapolates without structural/fault constraints; it is not a certified geological solid.',
    'Mine planning → Pit optimization uses undiscounted maximum closure on a complete, world-axis, equal-size parent grid with all grades present.',
    'Pit prices are per project grade-unit × tonne. MILP scheduling uses price per tonne of metal. Unit conversion is not automatic.',
    'The pit tool does not perform scheduling, NPV, ramp design or Whittle benchmarking. Check the stated limits.']),
'start': ('Starting RAINYMINE', [
    'Start-Windows.bat launches source; Rainymine.exe launches the installed or portable application.',
    'The initial project is a synthetic example. Choose Project → New before importing your own data.',
    'Import collars → surveys → assays / lithology, then save a .rmine project.']),
'import': ('CSV import and column mapping', [
    'Choose the appropriate collar, survey, assay or lithology import in Project or Drilling.',
    'Save CSV as CSV UTF-8. For .xlsx use Drilling → Excel import. Header names must be non-empty and unique.',
    'Map each source column to one required field. Check delimiter, decimal notation, units and identifiers in the preview.',
    'Review validation errors before applying. Keep an independent copy of the source data; import does not certify geological quality.']),
'project': ('Saving and restoring projects', [
    'Save with Project → Save or Ctrl+S; use Save as to make a separate .rmine copy.',
    'Open a saved .rmine project through Project → Open. Keep external source files and regular backups.',
    'An autosave is a recovery copy, not a substitute for verified project backups. Use a separate copy when reverting versions.']),
'render': ('Black or empty 3D viewport', [
    'Launch the CPU rendering shortcut or Rainymine-Software.bat and retain the complete software-rendering folder.',
    'Try Fit all, check layer visibility and restore the 3D view. A section or cutaway may hide geometry.',
    'Do not replace system DLLs manually. Record the application version, Windows/GPU details and reproduction steps for support.']),
'crs': ('Coordinate reference systems', [
    'Confirm source CRS, axis order and metre units before combining files.',
    'Use Project → Transform CRS for an explicit supported conversion. Editing a CRS description alone does not transform coordinates.',
    'Check control points against a trusted reference and keep the original project. Local 3D origin shifting is a rendering precision measure, not a CRS conversion.']),
'drillhole': ('Drillholes and assay coverage', [
    'Import unique collar IDs, then surveys, assays and lithology using the same IDs.',
    'Check interval order, overlaps, end-of-hole depth and unsampled intervals using the quality tools.',
    'Composite values use available sample support. Missing intervals are not assumed to be zero. Laboratory controls and geological review remain separate.']),
'block': ('Creating a block model', [
    'Use Block model → Create block model, configure estimation method, search radii, sample requirements and composites.',
    'Set bounds, block size, grid orientation and optional domain. Check CRS, units and support before calculating.',
    'Use variograms, cross-validation and external benchmarks to evaluate results. Unestimated blocks retain missing grades.',
    'A numerical model is unclassified and does not establish mineral resources or reserves.']),
'subblock': ('Sub-blocks and planar fault barriers', [
    'Create a fault plane in Block model, then select a domain and sub-block level when estimating.',
    'Levels 0–3 use finest-centre sampling and sibling coalescing with finite block limits. Boundary geometry is approximate.',
    'Fault planes are estimation barriers without displacement or a full structural model. A display-only example fault does not constrain grades.',
    'Inspect support, zone identifiers and volumes. Rotated/sub-block models are not supported by the parent-grid scheduling tool.']),
'view': ('3D selection and sections', [
    'Use View for layer properties, saved sections, X/Y/Z slices and split viewports.',
    'Click a block or drillhole to inspect actual project attributes. Measurement mode changes click behavior.',
    'PageUp / PageDown step through sections. Use 3D, Top, Front and Fit all camera controls.',
    'Grid, block edges and cutaway are display controls; they do not alter source grades. Rotated-grid slices use local grid axes.']),
'haul': ('Road and haulage scenarios', [
    'Create an open XYZ string using Geology → String / Polygon.',
    'Choose Mine planning → Road / Haulage and select that string.',
    'Enter width, gradient limit, payload, fleet size, loaded/empty speeds, loading/unloading/wait time, shift length and utilization.',
    'Excess gradient stops the fleet calculation. This is a constant-speed average-cycle scenario, not an engineered ramp or dispatch model.']),
'optimization': ('Running MILP scheduling', [
    'Use a world-axis parent grid. Rotated and sub-block scheduling is unsupported.',
    'Mine planning → MILP optimization requires density, cutoff, metal price, mining/processing/haul costs, recovery, capacities, periods and discount rate.',
    'All monetary inputs must use the same currency. Set a solver time limit.',
    'Review solver status and mip_gap. A feasible incumbent at timeout is not proof of optimality.',
    'This is optional-task scheduling with vertical-column precedence, not global pit-shell, stockpile or network optimization.']),
'benchmark': ('External reference comparison', [
    'Block model → External benchmark accepts a reference x,y,z,grade CSV with matching CRS, units and support.',
    'Set coordinate, absolute grade and relative grade tolerances.',
    'A numerical pass requires complete one-to-one matching and estimated grades. Missing or duplicate coordinates cannot pass.',
    'A numerical pass is not independent geological certification. Data rights, reference provenance and professional review are separate.']),
'ai': ('Local assistant setup', [
    'Use Initial setup to download the pinned engine and model once; the download requires internet access.',
    'After SHA256 verification the assistant runs locally. Ollama and API keys are not required.',
    'Use Choose files to select an existing GGUF and llama-server installation.',
    'The assistant answers application-operation questions from reviewed guides only. It cannot change calculations, delete files or run shell commands.'])
}


def localize(topic, locale):
    if locale != 'en':
        return topic
    title, steps = HELP[topic['id']]
    return dict(topic, title=title, steps=steps)
