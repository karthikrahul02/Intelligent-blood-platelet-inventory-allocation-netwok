import sys
import os
from descriptive_treatments import run_treatment_analysis

# Check if command-line arguments provided
if len(sys.argv) < 3:
    print("Usage: python run_treatment_analysis.py <input_csv_path> <output_directory>")
    print("Example: python run_treatment_analysis.py ../test_data_150patients.csv test_data_150patients")
    sys.exit(1)

input_file = sys.argv[1]
output_dir = sys.argv[2]

# Create output directory if it doesn't exist
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# Run the treatment statistics analysis
print(f"Starting treatment statistics analysis...")
print(f"Input file: {input_file}")
print(f"Output directory: {output_dir}")

treatment = run_treatment_analysis(input_file, output_dir=output_dir)

print(f"\nAnalysis complete! Results saved to:")
print(f"  - {output_dir}/treatment_statistics_detailed.json")
print(f"  - {output_dir}/treatment_statistics_administration_level.txt")
print(f"  - {output_dir}/treatment_statistics_patient_level.txt")
print(f"  - {output_dir}/treatment_statistics_combined.txt")
