(function () {
    'use strict';
    angular
        .module('bpApp', ['ngMaterial'])
        .controller('BlueprintController', BlueprintController)
        .filter('orderObjectBy',
            function() {
                return function(items, field, reverse) {
                    var filtered = [];
                    angular.forEach(items,
                        function(item) {
                            filtered.push(item);
                        });
                    filtered.sort(function(a, b) {
                        return (a[field] > b[field] ? 1 : -1);
                    });
                    if (reverse) filtered.reverse();
                    return filtered;
                };
            });


    function BlueprintController($scope, $http) {
        var self = this;

        self.selectedItem = null;
        self.compressMinerals = true;
        self.materialList = {};
        self.bpcList = {};
        self.stationActivities = {};

        self.mfgSystem = {
            SystemId: 30002019,
            SystemName: "F-NMX6"
        };

        self.importSystem = {
            SystemId: 30000142,
            SystemName: "Jita"
        };

        self.importStation = {
            StationId: 60003760,
            StationName: "Jita IV - Moon 4 - Caldari Navy Assembly Plant"
        }

        self.findBlueprints = findBlueprints;
        self.findSystems = findSystems;
        self.findStations = findStations;
        self.updateSystemRates = updateSystemRates;
        self.addBlueprint = addBlueprint;
        self.calcTabs = printTabs;
        self.refreshMaterials = refreshMaterials;
        self.printTabs = printTabs;
        self.summarizeBlueprints = summarizeBlueprints;
        

        self.selectedBlueprints = [];
        self.baseCostCache = {};

        // addBlueprint(24483);
        updateSystemRates();

        function updateSystemRates() {
            if (!self.mfgSystem) return;

            $http.get('https://api.eve-industry.org/system-cost-index.xml', { params: { name: self.mfgSystem.SystemName } })
                .then(function (response) {
                    var dom = parseXml(response.data);
                    var activities = dom.getElementsByTagName('activity');
                    for (var i = 0; i < activities.length; i++) {
                        var activity = activities[i];
                        self.stationActivities[activity.getAttribute("name")] = parseFloat(activity.innerHTML);
                    }
                });
        }

        function summarizeBlueprints() {
            calculateJobBaseCosts()
                .then(function() {
                    var bpViewModel = {
                        MfgSystemCostIndex: self.stationActivities["Manufacturing"],
                        CompressMinerals: self.compressMinerals,
                        PurchaseStationId: self.importStation.StationId,
                        Blueprints: stripNonModelValues(self.selectedBlueprints)
                    };

                    fetchSummaryView(bpViewModel);
                });
        }

        function stripNonModelValues(mats) {
            var matList = [];

            for (var i = 0; i < mats.length; i++) {
                var mat = angular.copy(mats[i]);

                if (mat["ReducedQty"]) {
                    mat["Qty"] = mat["ReducedQty"];
                }

                delete mat["TypeName"];
                delete mat["ReducedQty"];
                delete mat["TotalQty"];
                delete mat["Volume"];
                delete mat["Skills"];

                mat.Materials = stripNonModelValues(mat.Materials);

                matList.push(mat);
            }

            return matList;
        }

        function calculateJobBaseCosts() {
            var names = "";

            var bpcs = {};

            var gatherBpcs = function(mat) {
                if (mat.Materials.length) {
                    if (!bpcs[mat.TypeName]) bpcs[mat.TypeName] = [];

                    bpcs[mat.TypeName].push(mat);

                    for (var i = 0; i < mat.Materials.length; i++) {
                        gatherBpcs(mat.Materials[i]);
                    }
                }
            };

            for (var i = 0; i < self.selectedBlueprints.length; i++) {
                var bp = self.selectedBlueprints[i];

                gatherBpcs(bp);
            }

            for (var name in bpcs) {
                if (!bpcs.hasOwnProperty(name)) continue;

                if (names) names+= ",";

                names += name;
            }

            return $http.get('https://api.eve-industry.org/job-base-cost.xml', { params: { names: names } })
                .then(function (response) {
                    var dom = parseXml(response.data);
                    var costs = dom.getElementsByTagName('job-base-cost');
                    for (var i = 0; i < costs.length; i++) {
                        var cost = costs[i];
                        var name = cost.getAttribute("name").replace(" Blueprint", "");

                        for (var j = 0; j < bpcs[name].length; j++) {
                            bpcs[name][j].JobBaseCost = parseFloat(cost.innerHTML);
                        };
                    }
                });
        }

        function addBlueprint(typeId) {
            if (!typeId) return;

            var bpDetails = getBlueprint(typeId);

            bpDetails.then(function (d) {
                refreshMaterials(d);
                self.selectedBlueprints.push(d);
            });
        }

        function refreshMaterials(mat) {
            var reducedQty = isNaN(mat.ReducedQty) ? mat.Qty : mat.ReducedQty;
            var ttlQty = isNaN(mat.TotalQty) ? mat.Qty : mat.TtlQty;
            var me = mat.MaterialEfficiency;
            var materials = mat.Materials;

            for (var i = 0; i < materials.length; i++) {
                var childMat = materials[i];

                childMat.TotalQty = childMat.Qty * ttlQty;
                childMat.ReducedQty = reducedQty * Math.ceil(childMat.Qty * (1 - me * .01));

                refreshMaterials(childMat);
            }
        }

        function printTabs(tabs) {
            return "&nbsp;&nbsp;".repeat(tabs*1);
        }

        function fetchSummaryView(viewModel) {
            return $http.post('/Calculator/GetBlueprintSummary', { viewModel: viewModel })
                .then(function(response) {
                    $('#summary').html(response.data);
                });
        }

        function findBlueprints(query) {
            return $http.get('/Calculator/GetBlueprints', { params: { prefix: query } })
                .then(function (response) {
                    return response.data;
                });
        }

        function findSystems(query) {
            return $http.get('/Calculator/GetSystems', { params: { prefix: query } })
                .then(function(response) {
                    return response.data;
                });
        }

        function findStations(systemId, query) {
            return $http.get('/Calculator/GetStations', { params: { systemId: systemId, prefix: query } })
                .then(function (response) {
                    return response.data;
                });
        }

        function getBlueprint(typeId) {
            return $http.get('/Calculator/GetBlueprintDetails', { params: { typeId: typeId } })
                .then(function(response) {
                    return response.data;
                });
        }

        function parseXml(xml) {
            var dom;
            if (typeof DOMParser !== "undefined") {
                var parser = new DOMParser();
                dom = parser.parseFromString(xml, "text/xml");
            }
            else {
                var doc = new ActiveXObject("Microsoft.XMLDOM");
                doc.async = false;
                dom = doc.loadXML(xml);
            }

            return dom;
        }

    }
})();
