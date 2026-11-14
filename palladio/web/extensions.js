import {TransferTools} from './transfer.js';

// Feature panels share the same revision-aware workspace actions.
export class Extensions {
  constructor(find,hooks) {this.panels=[new TransferTools(find,hooks)];}
  render() {for(const panel of this.panels)panel.render?.();}
  sync() {for(const panel of this.panels)panel.sync?.();}
}
