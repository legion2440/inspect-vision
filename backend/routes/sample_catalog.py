"""Pinned operator showcase metadata.

This catalog is intentionally separate from backend/samples/demo: the VisA demo
corpus is audit/runtime evidence, while these records are the operator-facing
Samples page.
"""

MVTEC_REVISION = "e88b7bd615ad582b0a7e8238066a9fb293a072b4"
SPECIALIST_ASSET_COMMIT = "f82fe4645ada00d5b01a16b9a05b2ea36795cce2"

DATASETS = [
    {"id": "mvtec-ad", "name": "MVTec Anomaly Detection Dataset", "attribution": "MVTec Anomaly Detection Dataset (MVTec AD), CC BY-NC-SA 4.0."},
    {"id": "gkn-blade-v1", "name": "GKN Blade Surface Defect Dataset", "attribution": "GKN Blade Surface Defect Dataset V1 by Qianyu Zhou, CC BY 4.0."},
    {"id": "plos-neu-steel-figure-v1", "name": "Six Types of Metal Surface Defects, Figure 3", "attribution": "Xu, Y., Jiao, P., & Liu, J. (2023), PLOS ONE, CC BY 4.0."},
    {"id": "hu-infrastructure-cracks-v1", "name": "HU Infrastructure Cracks Dataset", "attribution": "HU Infrastructure Cracks Dataset, The Hashemite University, CC BY 4.0."},
]

SAMPLES = [
    {"id":"mvtec-bottle-good-000","domain":"Bottle","recommendedModelId":"bayespfl-general-v1","datasetId":"mvtec-ad","productName":"Bottle","condition":"good","sourceLabels":["good"],"sourcePath":"MVTec-AD/bottle/test/good/000.png","filename":"mvtec-bottle-good-000.png","mediaType":"image/png"},
    {"id":"mvtec-bottle-broken-large-000","domain":"Bottle","recommendedModelId":"bayespfl-general-v1","datasetId":"mvtec-ad","productName":"Bottle","condition":"bad","sourceLabels":["broken large"],"sourcePath":"MVTec-AD/bottle/test/broken_large/000.png","filename":"mvtec-bottle-broken-large-000.png","mediaType":"image/png"},
    {"id":"mvtec-capsule-good-000","domain":"Capsule","recommendedModelId":"bayespfl-general-v1","datasetId":"mvtec-ad","productName":"Capsule","condition":"good","sourceLabels":["good"],"sourcePath":"MVTec-AD/capsule/test/good/000.png","filename":"mvtec-capsule-good-000.png","mediaType":"image/png"},
    {"id":"mvtec-capsule-crack-006","domain":"Capsule","recommendedModelId":"bayespfl-general-v1","datasetId":"mvtec-ad","productName":"Capsule","condition":"bad","sourceLabels":["crack"],"sourcePath":"MVTec-AD/capsule/test/crack/006.png","filename":"mvtec-capsule-crack-006.png","mediaType":"image/png"},
    {"id":"mvtec-screw-good-001","domain":"Screw","recommendedModelId":"bayespfl-general-v1","datasetId":"mvtec-ad","productName":"Screw","condition":"good","sourceLabels":["good"],"sourcePath":"MVTec-AD/screw/test/good/001.png","filename":"mvtec-screw-good-001.png","mediaType":"image/png"},
    {"id":"mvtec-screw-manipulated-front-012","domain":"Screw","recommendedModelId":"bayespfl-general-v1","datasetId":"mvtec-ad","productName":"Screw","condition":"bad","sourceLabels":["manipulated front"],"sourcePath":"MVTec-AD/screw/test/manipulated_front/012.png","filename":"mvtec-screw-manipulated-front-012.png","mediaType":"image/png"},
    {"id":"mvtec-metal-nut-good-000","domain":"Metal nut","recommendedModelId":"bayespfl-general-v1","datasetId":"mvtec-ad","productName":"Metal nut","condition":"good","sourceLabels":["good"],"sourcePath":"MVTec-AD/metal_nut/test/good/000.png","filename":"mvtec-metal-nut-good-000.png","mediaType":"image/png"},
    {"id":"mvtec-metal-nut-bent-000","domain":"Metal nut","recommendedModelId":"bayespfl-general-v1","datasetId":"mvtec-ad","productName":"Metal nut","condition":"bad","sourceLabels":["bent"],"sourcePath":"MVTec-AD/metal_nut/test/bent/000.png","filename":"mvtec-metal-nut-bent-000.png","mediaType":"image/png"},
    {"id":"steel-good-img4685","domain":"Steel Surface","recommendedModelId":"neu-defect-yolov8","datasetId":"gkn-blade-v1","productName":"Steel surface","condition":"good","sourceLabels":["Good"],"filename":"steel-good-img4685.jpg","mediaType":"image/jpeg"},
    {"id":"steel-inclusion-plos-fig3b","domain":"Steel Surface","recommendedModelId":"neu-defect-yolov8","datasetId":"plos-neu-steel-figure-v1","productName":"Steel surface","condition":"bad","sourceLabels":["inclusion"],"filename":"steel-inclusion-plos-fig3b.png","mediaType":"image/png"},
    {"id":"steel-scratch-img2113","domain":"Steel Surface","recommendedModelId":"neu-defect-yolov8","datasetId":"gkn-blade-v1","productName":"Steel surface","condition":"bad","sourceLabels":["Scratch"],"filename":"steel-scratch-img2113.jpg","mediaType":"image/jpeg"},
    {"id":"concrete-cr01-transverse","domain":"Concrete & Structural Cracks","recommendedModelId":"concrete-crack-yolov8","datasetId":"hu-infrastructure-cracks-v1","productName":"Concrete surface","condition":"bad","sourceLabels":["pavement","transverse","moderate"],"filename":"concrete-cr01-pavement-transverse.jpg","mediaType":"image/jpeg"},
    {"id":"concrete-cr26-longitudinal","domain":"Concrete & Structural Cracks","recommendedModelId":"concrete-crack-yolov8","datasetId":"hu-infrastructure-cracks-v1","productName":"Concrete surface","condition":"bad","sourceLabels":["wall","longitudinal","severe"],"filename":"concrete-cr26-wall-longitudinal.jpg","mediaType":"image/jpeg"},
    {"id":"concrete-cr43-diagonal","domain":"Concrete & Structural Cracks","recommendedModelId":"concrete-crack-yolov8","datasetId":"hu-infrastructure-cracks-v1","productName":"Concrete surface","condition":"bad","sourceLabels":["pavement","diagonal","severe"],"filename":"concrete-cr43-pavement-diagonal.jpg","mediaType":"image/jpeg"},
]
