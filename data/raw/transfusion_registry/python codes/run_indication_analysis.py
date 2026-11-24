import sys
import os
from descriptive_indications import run_indication_intervention_analysis

# Check if command-line arguments provided
if len(sys.argv) < 3:
    print("Usage: python run_indication_analysis.py <input_csv_path> <output_directory>")
    print("Example: python run_indication_analysis.py ../test_data_150patients.csv test_data_150patients")
    sys.exit(1)

input_file = sys.argv[1]
output_dir = sys.argv[2]

# Create output directory if it doesn't exist
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# Run the indication and intervention statistics analysis
print(f"Starting indication and intervention statistics analysis...")
print(f"Input file: {input_file}")
print(f"Output directory: {output_dir}")

ind_interv = run_indication_intervention_analysis(input_file, output_dir=output_dir)

print(f"\nAnalysis complete! Results saved to:")
print(f"  - {output_dir}/indication_intervention_statistics_detailed.json")
print(f"  - {output_dir}/indication_intervention_statistics_administration_level.txt")
print(f"  - {output_dir}/indication_intervention_statistics_patient_level.txt")
print(f"  - {output_dir}/indication_intervention_statistics_combined.txt")
