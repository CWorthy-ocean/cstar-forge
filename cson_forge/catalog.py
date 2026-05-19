import os, fsspec
from pathlib import Path

# import some python package that keeps track of/enforces a hierachical file system?
#  catalog: 

class DomainCatalog():
    '''C-Star DomainCatalog track handles the hierachical system of validated/registerd "domains." 
    The DomainCatalog is designed to hold, at the root, models and model domains that together describe
    "validated" C-Star model solutions, where validated indicates model review and reflections (e.g. 
    input considerations/deviations rom C-Star default processing, outputs, intended use, uncertainty, 
    caveats) descrbed in catalog metadata.

    The base of a given catalog (self.catalog_root) is intended to be somewhere in the local file system,
    perhaps a git repository, or a web address.

    The DomainCatalog can process models, blueprints, and observations present in the catalog (report 
    those available, returing yaml-based schema for particular named <model, domain, observation>).

    Returned domains can be combined with models using forge to develop blueprints for new C-Star
    simulations on new machines. Archived blueprints can be run directly if all domain assests and 
    the orginal run machine/setup/container are available.

    The DomainCatalog can also "register" new domains, which consists of adding required dmoain metadata,
    linking non-forge default generated files (e.g. groomed grids, or other input files) to persistent
    copyies/storage, and optionally copying the domain an alternate catalog root (e.g. from local storage
    to github or other service)

    The domain catalog should probably abstract a storage_service concept, were writing and reading domain
    assets happen through the service (e.g. local gile systme github...)

    '''

    catalog_root: None | Path | str   # {Path, str, github url}
    cat: None | fsspec.filesystem       # fsspec instance of this catalog's filesystem

    def __init__(catalog_root=None):
                
        if catalog_root is None:
            # find directory of this file (__main__?), set catalog root to <this_dir>/calaog
            pass
        else:
            # typcheck for {github url; <Path, str> exists ..}                 
            self.catalog_root = catalog_root
            self.cat = self.infer_service()

        # scan for required directry structure, if it doesn't exist, create it?
        # While scanning, catalog file list of yamls in catalog/models, catalog/blueprints, 
        # catalog/domains
        self._scan_domains()
        self._scan_blueprints()
        self._scan_models()

    def infer_service():
        # find the setup the service that feeds us catalog files
        if not isinstance(self.catalog_root, Path):
            if isinstance(self.catalog_root, str):
                if 'github' in self.catalog_root:
                    return fsspec.filesystem('github', root=self.catalog_root)
                if self.catalog_root.startswith('http'):
                    return fsspec.filesystem('http', root=self.catalog_root)
                else:
                    return fsspec.filesystem('file', root=self.catalog_root)
            raise ValueError(f'Could not infer serice from catalog_root: {self.catalog_root}')            
        else:
            return fsspec.filesystem('file', root=catalog_root)

    def _scan_domains():
        self._domains = []
        for domain in self.catalog_root.glob("catalog/domains/*.yml"):
            self._domains.append(domain)

    def _scan_blueprints():
        pass  # add exising functionaliy to recusively return build blueprints, organized by domain name

    def _scan_models():
        '''scan the models.yaml, essential a database'''
        pass # scan the models.yaml, essential a database

    def register_domain(builder: CstarSpecBuilder):
        ''' Create a new domain by copying information from a CstarSpecBuilder ... somhow this has 
        to be called by CstarSpecBuilder, as it will supply the builder paths.
        
        it is not clear exactly what this means. Soecbuilder is holdong everythng in memory
        '''
        pass

    def register_model():
        pass

    def add_to_domain(domain_name: str, item_key: str, item_value: any):
        pass

    def copy_domain(domain_name: str, catalog: DomainCatalog):
        pass

    def copy_model(model_name: str, catalog: DomainCatalog):
        pass

