"""IBM Quantum Configuration.

Configured with active credentials for IBM Quantum Platform.
DO NOT COMMIT REAL CREDENTIALS TO GIT.
"""

import os

# Active IBM Quantum API Key
IBM_QUANTUM_API_KEY = (
    os.environ.get("IBM_QUANTUM_API_KEY")
    or os.environ.get("QISKIT_IBM_TOKEN")
    or os.environ.get("IBMQ_TOKEN")
    or "U6v8fUrcKKVIKCeFMphpK1LK4Qb2letO1C7SbFadCuId"
)

# Active IBM Quantum Instance CRN
IBM_QUANTUM_INSTANCE = (
    os.environ.get("IBM_QUANTUM_INSTANCE")
    or "crn:v1:bluemix:public:quantum-computing:us-east:a/08cec6aecd2d4add8629135cb186d019:d5c72872-e0fb-4d51-996c-53f3244aebf5::"
)

# Selected IBM Quantum hardware backend (e.g. 'ibm_brisbane', 'ibm_kyoto', 'ibm_sherbrooke', 'ibm_torino', 'ibm_fez')
# Set to None to automatically pick the least busy operational real hardware backend,
# or set to a specific hardware backend name.
IBM_QUANTUM_BACKEND = os.environ.get("IBM_QUANTUM_BACKEND") or None
