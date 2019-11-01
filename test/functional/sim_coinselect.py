#! /usr/bin/env python3
from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import *
from collections import deque
from statistics import mean, stdev
from decimal import *
import pprint

class CoinSelectionSimulation(BitcoinTestFramework):
    def set_test_params(self):
        self.num_nodes = 1
        self.setup_clean_chain = True
        self.extra_args = [["-dustrelayfee=0", "-maxtxfee=1"]]

    def run_test(self):
        # Decimal precision
        getcontext().prec = 12

        # Make two wallets
        self.nodes[0].createwallet('funder')
        self.nodes[0].createwallet('tester')
        funder = self.nodes[0].get_wallet_rpc('funder')
        tester = self.nodes[0].get_wallet_rpc('tester')

        # Check that there's no UTXO on the wallets
        assert_equal(len(funder.listunspent()), 0)
        assert_equal(len(tester.listunspent()), 0)

        self.log.info("Mining blocks for node0 to be able to send enough coins")

        gen_addr = funder.getnewaddress()
        funder.generatetoaddress(600, gen_addr) # > 14,000 BTC
        withdraw_address = funder.getnewaddress()
        deposit_address = tester.getnewaddress()

        scenario = 'sim_data.csv'

        self.log.info("Simulating using scenario: {}".format(scenario))
        payments = 0
        bnb_usage = 0
        with open('sim_results.txt', 'a+') as res:
            res.write('----BEGIN SIMULATION RESULTS----\nScenario: {}\n'.format(scenario))
            with open(scenario) as f:
                total_fees = Decimal()
                ops = 0
                count_sent = 0
                change_vals = []
                withdraws = 0
                input_sizes = []
                utxo_set_sizes = []
                count_change = 0
                count_received = 0;
                for line in f:
                    if ops % 500 == 0:
                        if ops > 0:
                            self.log.info("{} operations performed so far".format(ops))

                            # Find change stats
                            if len(change_vals) > 0:
                                change_vals = sorted(change_vals)
                                min_change = Decimal(change_vals[0])
                                max_change = Decimal(change_vals[-1])
                                mean_change = Decimal(mean(change_vals))
                                stdev_change = Decimal(stdev(change_vals))
                            else:
                                min_change = 0
                                max_change = 0
                                mean_change = 0
                                stdev_change = 0

                            # Remaining utxos and fee stats
                            remaining_utxos = tester.listunspent()
                            cost_to_empty = Decimal(-1 * len(remaining_utxos) * 148 * 0.00001 / 1000)
                            total_cost = total_fees + cost_to_empty

                            # input stats
                            input_sizes = sorted(input_sizes)
                            min_input_size = Decimal(input_sizes[0])
                            max_input_size = Decimal(input_sizes[-1])
                            mean_input_size = Decimal(mean(input_sizes))
                            stdev_input_size = Decimal(stdev(input_sizes))

                            result_str = "| {} | {:.8f} | {:.2f} | {} | {} | {} | {} | {:.8f} | {:.8f} | {:.8f} | {:.8f} | {:.8f} | {:.8f} | {:.8f} | {:.8f} | {:.8f} | {} | {} | {:.8f} | {:.8f} | {} |".format( \
                                scenario, tester.getbalance(), Decimal(mean(utxo_set_sizes)), len(remaining_utxos), count_received, count_sent, \
                                payments, len(change_vals), min_change, max_change, mean_change, stdev_change, total_fees, Decimal(total_fees / withdraws), \
                                cost_to_empty, total_cost, min_input_size, max_input_size, mean_input_size, stdev_input_size, bnb_usage)
                            res.write('{}\n'.format(result_str))

                    # Make deposit or withdrawal
                    val_str, fee_str = line.rstrip().lstrip().split(',')
                    value = Decimal(val_str)
                    feerate = Decimal(fee_str)
                    if value > 0:
                        try:
                            # deposit
                            funder.sendtoaddress(deposit_address, value)
                            count_received += 1
                        except JSONRPCException as e:
                            self.log.info("Failure on op {} with funder sending {} with error {}".format(ops, value, str(e)))
                    if value < 0:
                        try:
                            # Withdraw
                            value = value * -1
                            prev_bal = tester.getbalance() - total_fees
                            tester.settxfee(feerate)
                            txid = tester.sendtoaddress(withdraw_address, value)
                            withdraws += 1
                            # Get fee info
                            gettx = tester.gettransaction(txid)
                            total_fees += gettx['fee']
                            # Info about tx itself
                            decoded_tx = tester.decoderawtransaction(gettx['hex'])
                            # Spend utxo counts and input info
                            count_sent += len(decoded_tx['vin'])
                            input_sizes.append(len(decoded_tx['vin']))
                            # Change info
                            if len(decoded_tx['vout']) > 1:
                                for out in decoded_tx['vout']:
                                    if out['scriptPubKey']['addresses'][0] != withdraw_address:
                                        change_vals.append(out['value'])
                                        count_change += 1
                            else:
                                bnb_usage += 1
                            payments += 1
                        except JSONRPCException as e:
                            self.log.info("Failure on op {} with tester sending {} with error {}".format(ops, value, str(e)))
                    utxo_set_sizes.append(len(tester.listunspent(0)))
                    funder.generatetoaddress(1, gen_addr)
                    ops += 1

            # Find change stats
            if len(change_vals) > 0:
                change_vals = sorted(change_vals)
                min_change = Decimal(change_vals[0])
                max_change = Decimal(change_vals[-1])
                mean_change = Decimal(mean(change_vals))
                stdev_change = Decimal(stdev(change_vals))
            else:
                min_change = 0
                max_change = 0
                mean_change = 0
                stdev_change = 0

            # Remaining utxos and fee stats
            remaining_utxos = tester.listunspent()
            cost_to_empty = Decimal(-1 * len(remaining_utxos) * 148 * 0.00001 / 1000)
            total_cost = total_fees + cost_to_empty

            # input stats
            input_sizes = sorted(input_sizes)
            min_input_size = Decimal(input_sizes[0])
            max_input_size = Decimal(input_sizes[-1])
            mean_input_size = Decimal(mean(input_sizes))
            stdev_input_size = Decimal(stdev(input_sizes))

            # Print stuff
            result_str = "| {} | {:.8f} | {:.2f} | {} | {} | {} | {} | {:.8f} | {:.8f} | {:.8f} | {:.8f} | {:.8f} | {:.8f} | {:.8f} | {:.8f} | {:.8f} | {} | {} | {:.8f} | {:.8f} | {} |".format( \
                scenario, tester.getbalance(), Decimal(mean(utxo_set_sizes)), len(remaining_utxos), count_received, count_sent, \
                payments, len(change_vals), min_change, max_change, mean_change, stdev_change, total_fees, Decimal(total_fees / withdraws), \
                cost_to_empty, total_cost, min_input_size, max_input_size, mean_input_size, stdev_input_size, bnb_usage)
            res.write('{}\n'.format(result_str))
            res.write('----END SIMULATION RESULTS----\n\n\n')
            self.log.info("| Simulation File | final value | mean #UTXO | final #UTXO | #received | #spent | #payments sent |"
                + "#changes created | min change | max change | mean change | stDev of change | "
                + "total fees | average fees | fees to spend remaining UTXO | total cost | "
                + "min input set | max input set | mean size of input set | stdev of input set size | BnB Usage |")
            self.log.info(result_str)

if __name__ == '__main__':
    CoinSelectionSimulation().main()
