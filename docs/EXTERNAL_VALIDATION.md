# External deposit validation — pending

The software supplies a numerical comparison workflow. No real-deposit dataset or independent geologist sign-off has been supplied, so independent validation is not completed.

1. Obtain written authorization to use an anonymized real-deposit collar/survey/assay/lithology/CRS dataset. Record origin, owner permission, anonymization and laboratory QA/QC.
2. Agree with an independent geologist on domains/fault assumptions, units, composite support, grid/sub-block geometry, covariance, search, top cuts, density and tolerances **before** testing.
3. Obtain reference outputs from an independently run, identified software/version or reviewed calculation. Do not export Rainymine results and call them an independent reference.
4. Import and save the Rainymine `.rmine` project, retaining input provenance and model run SHA256.
5. Export reference block centres/grades as UTF-8 `x,y,z,grade` CSV (all blocks, unique coordinates, same CRS/units/support). The current comparator checks grades at centres, not full topology, volumes, reserves or engineering.
6. Run the External Benchmark ribbon action, or `python scripts/compare_reference.py project.rmine reference.csv`. Review complete coverage, differences, tolerances and missing/unestimated blocks. Numeric agreement alone does not establish geological validity.
7. Have the independent reviewer document remaining differences, review provenance, geometry/tonnage, sensitivities and sign/date their report outside the software. Archive the exact source/reference files and hashes with it.

Required evidence remains: authorized real-deposit data, independent reference, agreed tolerances, reviewed results and signed reviewer report. Synthetic tests in this repository are development controls, not independent deposit certification.
