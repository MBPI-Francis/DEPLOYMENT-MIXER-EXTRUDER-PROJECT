from sqlalchemy.orm import declarative_base

# this will be used for the rest of the based on the models
Base = declarative_base()

from .User import User, AuthLog
from .Mixer import (MixerMachine,
                    MixerHeader,
                    MixerDetail)
from .ProdDatabase import (TblFormula01,
                           TblFormula02,
                           TblProd01,
                           TblProd02)

from .RawMaterials import RawMaterials

from .ExtruderConfig import (ExtruderMachine,
                             Zone,
                             Resin,
                             ResinParams,
                             ProcessingParams)

from .Customers import Customer

from .ProductionEmployees import ProductionEmployee, EmployeePosition

from . ExtruderCore import (ExtruderPersonnel,
                            ExtruderOutput,
                            ExtruderFormData,
                            MachineTemp,
                            MachineConfig,
                            UsedMaterial,
                            PurgingDetail,
                            ScreenSize
                            )


