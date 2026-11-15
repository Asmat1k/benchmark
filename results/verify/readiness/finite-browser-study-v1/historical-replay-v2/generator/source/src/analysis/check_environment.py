from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
import seaborn as sns

output = Path(sys.argv[1])
data = pd.DataFrame({"x": np.arange(3), "y": [2, 1, 3]})
sns.lineplot(data=data, x="x", y="y", errorbar=None)
for extension in ("png", "svg", "pdf"):
    path = output / f"synthetic.{extension}"
    plt.savefig(path)
    if not path.stat().st_size:
        raise ValueError(f"empty figure: {path}")
print(sys.version, np.__version__, scipy.__version__, pd.__version__, plt.matplotlib.__version__, sns.__version__)
