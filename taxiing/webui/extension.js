console.log('Loading TAXII NG WebUI');

(function() {

function TAXIINgSideConfigController($scope, MinemeldConfigService, MineMeldRunningConfigStatusService,
                                    toastr, $modal, ConfirmService, $timeout) {
    var vm = this;

    // side config settings
    vm.verify_cert = undefined;
    vm.api_key = undefined;
    vm.username = undefined;
    vm.api_header = undefined;
    vm.password = undefined;

    vm.loadSideConfig = function() {
        var nodename = $scope.$parent.vm.nodename;

        MinemeldConfigService.getDataFile(nodename + '_side_config')
        .then((result) => {
            if (!result) {
                return;
            }

            if (result.api_key) {
                vm.api_key = result.api_key;
            } else {
                vm.api_key = undefined;
            }

            if (result.api_header) {
                vm.api_header = result.api_header;
            } else {
                vm.api_header = undefined;
            }

            if (result.username) {
                vm.username = result.username;
            } else {
                vm.username = undefined;
            }

            if (result.password) {
                vm.password = result.password;
            } else {
                vm.password = undefined;
            }

            if (typeof result.verify_cert !== 'undefined') {
                vm.verify_cert = result.verify_cert;
            } else {
                vm.verify_cert = undefined;
            }
        }, (error) => {
            toastr.error('ERROR RETRIEVING NODE SIDE CONFIG: ' + error.status);
            vm.api_key = undefined;
            vm.verify_cert = undefined;
        });
    };

    vm.saveSideConfig = function() {
        var side_config = {};
        var hup_node = undefined;
        var nodename = $scope.$parent.vm.nodename;

        if (vm.api_key) {
            side_config.api_key = vm.api_key;
        }
        if (vm.api_header) {
            side_config.api_header = vm.api_header;
        }

        if (vm.username) {
            side_config.username = vm.username;
        }
        if (vm.password) {
            side_config.password = vm.password;
        }

        if (typeof vm.verify_cert !== 'undefined') {
            side_config.verify_cert = vm.verify_cert;
        }

        return MinemeldConfigService.saveDataFile(
            nodename + '_side_config',
            side_config
        );
    };

    vm.setAPIKey = function() {
        var mi = $modal.open({
            templateUrl: '/extensions/webui/taxiingWebui/taxiing.miner.sak.modal.html',
            controller: ['$modalInstance', 'fieldName', TAXIINgAPIKeyController],
            controllerAs: 'vm',
            bindToController: true,
            backdrop: 'static',
            animation: false,
            resolve: {
                fieldName: () => 'API KEY'
            }
        });

        mi.result.then((result) => {
            vm.api_key = result.api_key;

            return vm.saveSideConfig().then((result) => {
                toastr.success('API KEY SET');
                vm.loadSideConfig();
            }, (error) => {
                toastr.error('ERROR SETTING API KEY: ' + error.statusText);
            });
        });
    };

    vm.setAPIHeader = function() {
        var mi = $modal.open({
            templateUrl: '/extensions/webui/taxiingWebui/taxiing.miner.su.modal.html',
            controller: ['$modalInstance', 'fieldName', TAXIINgUsernameController],
            controllerAs: 'vm',
            bindToController: true,
            backdrop: 'static',
            animation: false,
            resolve: {
                fieldName: () => 'API HEADER'
            }
        });

        mi.result.then((result) => {
            vm.api_header = result.username;

            return vm.saveSideConfig().then((result) => {
                toastr.success('API HEADER SET');
                vm.loadSideConfig();
            }, (error) => {
                toastr.error('ERROR SETTING API HEADER: ' + error.statusText);
            });
        });
    };

    vm.setPassword = function() {
        var mi = $modal.open({
            templateUrl: '/extensions/webui/taxiingWebui/taxiing.miner.sak.modal.html',
            controller: ['$modalInstance', 'fieldName', TAXIINgAPIKeyController],
            controllerAs: 'vm',
            bindToController: true,
            backdrop: 'static',
            animation: false,
            resolve: {
                fieldName: () => 'PASSWORD'
            }
        });

        mi.result.then((result) => {
            vm.password = result.api_key;

            return vm.saveSideConfig().then((result) => {
                toastr.success('PASSWORD SET');
                vm.loadSideConfig();
            }, (error) => {
                toastr.error('ERROR SETTING PASSWORD: ' + error.statusText);
            });
        });
    };

    vm.setUsername = function() {
        var mi = $modal.open({
            templateUrl: '/extensions/webui/taxiingWebui/taxiing.miner.su.modal.html',
            controller: ['$modalInstance', 'fieldName', TAXIINgUsernameController],
            controllerAs: 'vm',
            bindToController: true,
            backdrop: 'static',
            animation: false,
            resolve: {
                fieldName: () => 'USERNAME'
            }
        });

        mi.result.then((result) => {
            vm.username = result.username;

            return vm.saveSideConfig().then((result) => {
                toastr.success('USERNAME SET');
                vm.loadSideConfig();
            }, (error) => {
                toastr.error('ERROR SETTING USERNAME: ' + error.statusText);
            });
        });
    };

    vm.toggleCertificateVerification = function() {
        var p, new_value;

        if (typeof this.verify_cert === 'undefined' || this.verify_cert) {
            new_value = false;
            p = ConfirmService.show(
                'CERT VERIFICATION',
                'Are you sure you want to disable certificate verification ?'
            );
        } else {
            new_value = true;
            p = ConfirmService.show(
                'CERT VERIFICATION',
                'Are you sure you want to enable certificate verification ?'
            );
        }

        p.then((result) => {
            vm.verify_cert = new_value;

            return vm.saveSideConfig().then((result) => {
                toastr.success('CERT VERIFICATION TOGGLED');
                vm.loadSideConfig();
            }, (error) => {
                toastr.error('ERROR TOGGLING CERT VERIFICATION: ' + error.statusText);
            });
        });
    };

    vm.loadSideConfig();
}

function TAXIINgAPIKeyController($modalInstance, fieldName) {
    var vm = this;

    vm.fieldName = fieldName;

    vm.api_key = undefined;
    vm.api_key2 = undefined;

    vm.valid = function() {
        if (vm.api_key !== vm.api_key2) {
            angular.element('#fgPassword1').addClass('has-error');
            angular.element('#fgPassword2').addClass('has-error');

            return false;
        }
        angular.element('#fgPassword1').removeClass('has-error');
        angular.element('#fgPassword2').removeClass('has-error');

        if (!vm.api_key) {
            return false;
        }

        return true;
    };

    vm.save = function() {
        var result = {};

        result.api_key = vm.api_key;

        $modalInstance.close(result);
    }

    vm.cancel = function() {
        $modalInstance.dismiss();
    }
}

function TAXIINgUsernameController($modalInstance, fieldName) {
    var vm = this;

    vm.username = undefined;
    vm.fieldName = fieldName;

    vm.valid = function() {
        if (!vm.username) {
            return false;
        }

        return true;
    };

    vm.save = function() {
        var result = {};

        result.username = vm.username;

        $modalInstance.close(result);
    }

    vm.cancel = function() {
        $modalInstance.dismiss();
    }
}

angular.module('taxiingWebui', [])
    .controller('TAXIINgSideConfigController', [
        '$scope', 'MinemeldConfigService', 'MineMeldRunningConfigStatusService',
        'toastr', '$modal', 'ConfirmService', '$timeout',
        TAXIINgSideConfigController
    ])
    .config(['$stateProvider', function($stateProvider) {
        $stateProvider.state('nodedetail.taxiinginfo', {
            templateUrl: '/extensions/webui/taxiingWebui/taxiing.miner.info.html',
            controller: 'NodeDetailInfoController',
            controllerAs: 'vm'
        });
    }])
    .run(['NodeDetailResolver', '$state', function(NodeDetailResolver, $state) {
        NodeDetailResolver.registerClass('taxiing.node.Miner', {
            tabs: [{
                icon: 'fa fa-circle-o',
                tooltip: 'INFO',
                state: 'nodedetail.taxiinginfo',
                active: false
            },
            {
                icon: 'fa fa-area-chart',
                tooltip: 'STATS',
                state: 'nodedetail.stats',
                active: false
            },
            {
                icon: 'fa fa-asterisk',
                tooltip: 'GRAPH',
                state: 'nodedetail.graph',
                active: false
            }]
        });

        // if a nodedetail is already shown, reload the current state to apply changes
        // we should definitely find a better way to handle this...
        if ($state.$current.toString().startsWith('nodedetail.')) {
            $state.reload();
        }
    }]);
})();
