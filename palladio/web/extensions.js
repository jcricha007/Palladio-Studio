import {WaterTools} from './water.js';
import {FoundationTools} from './foundations.js';
import {WallTools} from './walls.js';
import {TransferTools} from './transfer.js';
import {LayoutTools} from './layout.js';
import {RoofTools} from './roofs.js';
import {RoomTools} from './rooms.js';
import {DiagnosticsTools} from './diagnostics.js';
import {JobTools} from './jobs.js';
import {PresentationTools} from './presentation.js';
import {FinishTools} from './finishes.js';
import {PlantingTools} from './planting.js';

// Feature panels share the same revision-aware workspace actions.
export class Extensions {
  constructor(find,hooks) {this.jobs=new JobTools(find,hooks);this.panels=[new WaterTools(find,hooks),new FoundationTools(find,hooks),new WallTools(find,hooks),new DiagnosticsTools(find,hooks),new TransferTools(find,hooks),new LayoutTools(find,hooks),new RoofTools(find,hooks),new RoomTools(find,hooks),new PlantingTools(find,hooks),new FinishTools(find,hooks),new PresentationTools(find,hooks),this.jobs];}
  applyJob(plan){return this.jobs.apply(plan);}
  discardJob(plan){return this.jobs.discard(plan);}
  render() {for(const panel of this.panels)panel.render?.();}
  sync() {for(const panel of this.panels)panel.sync?.();}
}
