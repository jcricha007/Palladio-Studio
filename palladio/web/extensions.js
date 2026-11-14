import {TransferTools} from './transfer.js';
import {LayoutTools} from './layout.js';
import {RoofTools} from './roofs.js';
import {RoomTools} from './rooms.js';
import {FinishTools} from './finishes.js';
import {PlantingTools} from './planting.js';

// Feature panels share the same revision-aware workspace actions.
export class Extensions {
  constructor(find,hooks) {this.panels=[new TransferTools(find,hooks),new LayoutTools(find,hooks),new RoofTools(find,hooks),new RoomTools(find,hooks),new PlantingTools(find,hooks),new FinishTools(find,hooks)];}
  render() {for(const panel of this.panels)panel.render?.();}
  sync() {for(const panel of this.panels)panel.sync?.();}
}
